"""Servicio de validación presupuestal: registro del requerimiento y su semáforo.

Implementa el CU-03 (registrar requerimiento) con el CU-01 (validación automática) en una
sola transacción (RI-15): el requerimiento, sus ítems, su primer registro del historial y su
primera validación se confirman juntos o no se guarda nada.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio, NoEncontrado
from app.core.reloj import Reloj, fecha_local
from app.esquemas.requerimiento import (
    DocumentosEnvio,
    EnvioEntrada,
    Paso2Entrada,
    RequerimientoEntrada,
    ResultadoEnvio,
    ResultadoRegistro,
)
from app.modelos.presupuesto import CargaDatos, MetaPresupuestal, SaldoMeta
from app.modelos.requerimiento import (
    HistorialEtapa,
    Requerimiento,
    RequerimientoItem,
    ValidacionPresupuestal,
)
from app.repositorios.catalogos import RepositorioCatalogos
from app.repositorios.presupuesto import RepositorioPresupuesto
from app.repositorios.requerimientos import RepositorioRequerimientos
from app.seguridad.dependencias import UsuarioActual
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.validacion.monto import calcular_monto_estimado, verificar_tope_8_uit
from app.servicios.validacion.regla_semaforo import (
    EntradaSemaforo,
    ParametrosRegla,
    ResultadoSemaforo,
    SaldoVigente,
    evaluar_semaforo,
    opciones_de_ajuste,
)
from app.servicios.validacion.vigencia import SemaforoVigente, semaforo_vigente


class ServicioValidacion:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto | None = None) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto
        self._catalogos = RepositorioCatalogos(sesion)
        self._presupuesto = RepositorioPresupuesto(sesion)
        self._requerimientos = RepositorioRequerimientos(sesion)

    # --- Regla vigente ------------------------------------------------------------------
    def regla_vigente(self) -> tuple[int, ParametrosRegla]:
        regla = self._catalogos.regla_vigente()
        if regla is None:
            raise ErrorNegocio(503, "Servicio no disponible", "No hay una regla vigente.")
        return regla.id_regla, ParametrosRegla.desde_json(regla.parametros)

    # --- CU-03 + CU-01 --------------------------------------------------------------------
    def registrar(self, datos: RequerimientoEntrada, usuario: UsuarioActual) -> ResultadoRegistro:
        if usuario.id_unidad is None:  # RI-13
            raise ErrorNegocio(403, "Acceso denegado", "El usuario no tiene unidad orgánica.")
        momento = self._reloj()
        anio = fecha_local(momento).year
        id_regla, parametros = self.regla_vigente()

        meta = self._presupuesto.meta_activa(anio, datos.meta_codigo)
        if meta is None:
            raise DatosNoValidos("La meta no existe o no está activa en el ejercicio vigente.")
        monto = calcular_monto_estimado(datos.items)
        verificar_tope_8_uit(monto, parametros.tope_8_uit)
        if datos.fecha_necesidad < fecha_local(momento):
            raise DatosNoValidos("La fecha de necesidad no puede ser anterior a hoy.")
        id_pac_item = self._resolver_pac(anio, datos.pac_item_referencia)

        estado_inicial = self._catalogos.estado("REGISTRADO")
        if estado_inicial is None:
            raise ErrorNegocio(503, "Servicio no disponible", "Faltan los estados iniciales.")
        requerimiento = Requerimiento(
            codigo=self._requerimientos.siguiente_codigo(anio),
            id_unidad=usuario.id_unidad, id_meta=meta.id_meta, id_pac_item=id_pac_item,
            id_estado_actual=estado_inicial.id_estado,
            objeto_contratacion=datos.objeto_contratacion, descripcion=datos.descripcion,
            monto_estimado=monto, fecha_necesidad=datos.fecha_necesidad, fecha_registro=momento,
        )
        self._requerimientos.agregar(requerimiento)
        self._requerimientos.agregar(
            *(RequerimientoItem(id_requerimiento=requerimiento.id_requerimiento, **i.model_dump())
              for i in datos.items),
            HistorialEtapa(id_requerimiento=requerimiento.id_requerimiento,
                           id_estado=estado_inicial.id_estado, id_rol=usuario.id_rol,
                           fecha_hora=momento),
        )
        resultado, saldo, carga = self._validar(requerimiento, meta, id_regla, parametros, momento)
        self._registrar_en_bitacora(
            "REGISTRO_REQUERIMIENTO", requerimiento, usuario, momento,
            {"monto_estimado": str(monto), "items": len(datos.items)})
        self._registrar_validacion(requerimiento, usuario, momento, resultado,
                                   requerimiento.monto_estimado)
        self._sesion.commit()

        return ResultadoRegistro(
            requerimiento_id=requerimiento.id_requerimiento, codigo=requerimiento.codigo,
            monto_estimado=monto, estado_semaforo=resultado.estado, motivo=resultado.motivo,
            saldo_disponible_meta=resultado.saldo_disponible,
            previsto_en_pac=id_pac_item is not None,
            fecha_corte_datos=carga.fecha_corte if carga else None,
            opciones_ajuste=opciones_de_ajuste(resultado),
        )

    def _resolver_pac(self, anio: int, referencia: str | None) -> int | None:
        if referencia is None:
            return None
        carga_pac = self._presupuesto.ultima_carga_exitosa("SEACE", anio)
        item = self._presupuesto.pac_item(carga_pac.id_carga, referencia) if carga_pac else None
        if item is None:
            raise DatosNoValidos(f"El ítem {referencia} no figura en el PAC vigente.")
        return item.id_pac_item

    def revalidar(
        self, requerimiento: Requerimiento, usuario: UsuarioActual, momento: datetime,
        monto: Decimal | None = None,
    ) -> ResultadoSemaforo:
        """Nueva validación del mismo requerimiento: tras un ajuste (CU-05) o con el precio de
        mercado del cuadro comparativo (cambio 8 de la Práctica 7). Se agrega una validación
        nueva; las anteriores se conservan (RI-22) y la vigente es la más reciente (I-05)."""
        id_regla, parametros = self.regla_vigente()
        meta = self._sesion.get(MetaPresupuestal, requerimiento.id_meta)
        resultado, _, _ = self._validar(requerimiento, meta, id_regla, parametros, momento,
                                        monto)
        self._registrar_validacion(requerimiento, usuario, momento, resultado,
                                   monto or requerimiento.monto_estimado)
        return resultado

    def _registrar_validacion(
        self, requerimiento: Requerimiento, usuario: UsuarioActual, momento: datetime,
        resultado: ResultadoSemaforo, monto: Decimal,
    ) -> None:
        self._registrar_en_bitacora(
            "VALIDACION_SEMAFORO", requerimiento, usuario, momento,
            {"estado": str(resultado.estado), "motivo": str(resultado.motivo),
             "monto_evaluado": str(monto)})

    def _registrar_en_bitacora(
        self, accion: str, requerimiento: Requerimiento, usuario: UsuarioActual,
        momento: datetime, detalle: dict,
    ) -> None:
        if self._contexto is None:
            return
        bitacora.registrar(
            self._sesion, momento, self._contexto, accion, "EXITO",
            id_usuario=usuario.id_usuario, id_rol=usuario.id_rol,
            recurso_tipo="REQUERIMIENTO", recurso_id=requerimiento.id_requerimiento,
            detalle=detalle)

    def _validar(
        self, requerimiento: Requerimiento, meta: MetaPresupuestal, id_regla: int,
        parametros: ParametrosRegla, momento: datetime, monto: Decimal | None = None,
    ) -> tuple[ResultadoSemaforo, SaldoMeta | None, CargaDatos | None]:
        """CU-01: calcula el semáforo con la última carga del MEF y la regla vigente (RI-17)."""
        monto = monto if monto is not None else requerimiento.monto_estimado
        carga = self._presupuesto.ultima_carga_exitosa("MEF", meta.anio_fiscal)
        saldo = self._presupuesto.saldo(meta.id_meta, carga.id_carga) if carga else None
        vigente = None
        if saldo is not None and carga is not None and carga.fecha_corte is not None:
            vigente = SaldoVigente(saldo.pim, saldo.certificacion, saldo.compromiso_anual,
                                   carga.fecha_corte)
        resultado = evaluar_semaforo(EntradaSemaforo(
            monto=monto, saldo=vigente,
            previsto_en_pac=requerimiento.id_pac_item is not None,
            parametros=parametros, momento=momento,
        ))
        self._requerimientos.agregar(ValidacionPresupuestal(
            id_requerimiento=requerimiento.id_requerimiento,
            id_saldo=saldo.id_saldo if vigente and saldo else None, id_regla=id_regla,
            fecha_hora=momento, monto_evaluado=monto,
            estado_semaforo=resultado.estado, motivo=resultado.motivo,
        ))
        return resultado, saldo, carga

    # --- Paso 2 y envío (cambio 15 de la Práctica 7) ---------------------------------------
    def vigente(self, requerimiento: Requerimiento) -> tuple[SemaforoVigente, bool]:
        """Semáforo vigente (RI-20) e indicación de si lo confirmó Presupuesto."""
        validacion = self._requerimientos.ultima_validacion(requerimiento.id_requerimiento)
        if validacion is None:
            raise RuntimeError("Todo requerimiento tiene al menos una validación (R12).")
        decision = self._requerimientos.decision(validacion.id_validacion)
        resultado = decision.resultado if decision else None
        estado = semaforo_vigente(validacion.estado_semaforo, resultado)
        return estado, validacion.estado_semaforo == "AMBAR" and resultado == "CONFIRMADA"

    def guardar_paso_2(
        self, id_requerimiento: int, datos: Paso2Entrada, usuario: UsuarioActual
    ) -> Requerimiento:
        """«Guardar y continuar después»: guarda el paso 2 sin enviar; admite datos parciales."""
        requerimiento = self._requerimiento_con_paso_2_habilitado(id_requerimiento, usuario)
        self._aplicar_paso_2(requerimiento, datos)
        self._sesion.commit()
        return requerimiento

    def enviar(
        self, id_requerimiento: int, datos: EnvioEntrada, usuario: UsuarioActual
    ) -> ResultadoEnvio:
        """«Enviar a la Gerencia de Administración»: desde aquí corre su plazo de 24 horas."""
        requerimiento = self._requerimiento_con_paso_2_habilitado(id_requerimiento, usuario)
        self._aplicar_paso_2(requerimiento, datos)
        faltantes = self._faltantes_para_enviar(requerimiento, datos.documentos)
        if faltantes:
            self._sesion.rollback()
            raise DatosNoValidos("Complete el paso 2 antes de enviar: " + "; ".join(faltantes)
                                 + ".")
        requerimiento.fecha_envio = self._reloj()
        self._sesion.commit()
        return ResultadoEnvio(requerimiento_id=requerimiento.id_requerimiento,
                              codigo=requerimiento.codigo, fecha_envio=requerimiento.fecha_envio)

    def _requerimiento_con_paso_2_habilitado(
        self, id_requerimiento: int, usuario: UsuarioActual
    ) -> Requerimiento:
        requerimiento = self.obtener_para_usuario(id_requerimiento, usuario)
        estado = self._catalogos.estado("REGISTRADO")
        if estado is None or requerimiento.id_estado_actual != estado.id_estado:
            raise ErrorNegocio(409, "Conflicto",
                               "El paso 2 solo se completa con el requerimiento en Registrado.")
        if requerimiento.fecha_envio is not None:
            raise ErrorNegocio(409, "Conflicto",
                               "El requerimiento ya fue enviado a la Gerencia de Administración.")
        vigente, _ = self.vigente(requerimiento)
        if vigente != SemaforoVigente.VERDE:
            raise ErrorNegocio(409, "Conflicto",
                               "El paso 2 solo se habilita con semáforo vigente verde.")
        return requerimiento

    @staticmethod
    def _aplicar_paso_2(requerimiento: Requerimiento, datos: Paso2Entrada) -> None:
        items = {i.id_item: i for i in requerimiento.items}
        for entrada in datos.items:
            item = items.get(entrada.id_item)
            if item is None:
                raise DatosNoValidos(f"El ítem {entrada.id_item} no pertenece al requerimiento.")
            item.especificacion = entrada.especificacion or None
        requerimiento.plazo_entrega_dias = datos.plazo_entrega_dias
        requerimiento.lugar_entrega = datos.lugar_entrega or None

    @staticmethod
    def _faltantes_para_enviar(
        requerimiento: Requerimiento, documentos: DocumentosEnvio
    ) -> list[str]:
        faltantes = []
        if any(not i.especificacion for i in requerimiento.items):
            faltantes.append("falta la especificación técnica de algún ítem")
        if requerimiento.plazo_entrega_dias is None:
            faltantes.append("falta el plazo de entrega")
        if requerimiento.lugar_entrega is None:
            faltantes.append("falta el lugar de entrega")
        if not all(documentos.model_dump().values()):
            faltantes.append("marque los tres documentos que se adjuntan al expediente")
        return faltantes

    # --- CU-04: detalle ------------------------------------------------------------------
    def obtener_para_usuario(self, id_requerimiento: int, usuario: UsuarioActual) -> Requerimiento:
        """Verifica la pertenencia del recurso: el Área Usuaria solo ve los de su unidad.

        Responde 404 y no 403 para no revelar que el requerimiento existe (OWASP A01).
        """
        requerimiento = self._requerimientos.obtener(id_requerimiento)
        if requerimiento is None or (
            usuario.codigo_rol == "AU" and requerimiento.id_unidad != usuario.id_unidad
        ):
            raise NoEncontrado("El requerimiento no existe.")
        return requerimiento
