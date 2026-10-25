"""Servicio de validación presupuestal: registro del requerimiento y su semáforo.

Implementa el CU-03 (registrar requerimiento) con el CU-01 (validación automática) en una
sola transacción (RI-15): el requerimiento, sus ítems, su primer registro del historial y su
primera validación se confirman juntos o no se guarda nada.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio, NoEncontrado
from app.core.reloj import Reloj, fecha_local
from app.esquemas.requerimiento import RequerimientoEntrada, ResultadoRegistro
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
from app.servicios.validacion.monto import calcular_monto_estimado, verificar_tope_8_uit
from app.servicios.validacion.regla_semaforo import (
    EntradaSemaforo,
    ParametrosRegla,
    ResultadoSemaforo,
    SaldoVigente,
    evaluar_semaforo,
    opciones_de_ajuste,
)


class ServicioValidacion:
    def __init__(self, sesion: Session, reloj: Reloj) -> None:
        self._sesion = sesion
        self._reloj = reloj
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

    def _validar(
        self, requerimiento: Requerimiento, meta: MetaPresupuestal, id_regla: int,
        parametros: ParametrosRegla, momento: datetime,
    ) -> tuple[ResultadoSemaforo, SaldoMeta | None, CargaDatos | None]:
        """CU-01: calcula el semáforo con la última carga del MEF y la regla vigente (RI-17)."""
        carga = self._presupuesto.ultima_carga_exitosa("MEF", meta.anio_fiscal)
        saldo = self._presupuesto.saldo(meta.id_meta, carga.id_carga) if carga else None
        vigente = None
        if saldo is not None and carga is not None and carga.fecha_corte is not None:
            vigente = SaldoVigente(saldo.pim, saldo.certificacion, saldo.compromiso_anual,
                                   carga.fecha_corte)
        resultado = evaluar_semaforo(EntradaSemaforo(
            monto=requerimiento.monto_estimado, saldo=vigente,
            previsto_en_pac=requerimiento.id_pac_item is not None,
            parametros=parametros, momento=momento,
        ))
        self._requerimientos.agregar(ValidacionPresupuestal(
            id_requerimiento=requerimiento.id_requerimiento,
            id_saldo=saldo.id_saldo if vigente and saldo else None, id_regla=id_regla,
            fecha_hora=momento, monto_evaluado=requerimiento.monto_estimado,
            estado_semaforo=resultado.estado, motivo=resultado.motivo,
        ))
        return resultado, saldo, carga

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
