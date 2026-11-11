"""Aplicar ajuste sugerido ante un semáforo rojo (CU-05, RF-04; pantalla P05).

Opciones (Tabla 6 de la Práctica 7):
  - REFORMULAR: cambia lo que se pide, no el precio de lo que ya se pidió. Un ítem que se
    conserva solo puede bajar su cantidad y su precio unitario queda bloqueado (RI-26); para
    pedir otra cosa se reemplaza el ítem por uno nuevo con su precio y su fuente.
  - REPROGRAMAR: cambia la fecha de necesidad a una posterior.
  - NINGUNA: el área rechaza las opciones; el requerimiento queda en rojo y solo puede
    anularse (flujo alternativo 3a del CU-05).
Con REFORMULAR y REPROGRAMAR se ejecuta una nueva validación. El ajuste se registra una sola
vez por validación (R15) y no se modifica después (RI-22). Los ítems anteriores y los nuevos
quedan en la bitácora con su valor anterior y nuevo.
"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.errores import DatosNoValidos, ErrorNegocio
from app.core.reloj import Reloj, fecha_local
from app.esquemas.tramite import AjusteEntrada, ItemAjuste, ResultadoAjuste
from app.modelos.requerimiento import AjusteRequerimiento, Requerimiento, RequerimientoItem
from app.seguridad.dependencias import UsuarioActual
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto
from app.servicios.trazabilidad.maquina import MaquinaEstados
from app.servicios.validacion.monto import (
    calcular_monto_estimado,
    subtotal,
    verificar_tope_8_uit,
)
from app.servicios.validacion.servicio import ServicioValidacion
from app.servicios.validacion.situacion import situacion

MENSAJE_RI26 = ("No se puede cambiar el precio de un ítem que se conserva (RI-26): reduzca su "
                "cantidad o use «Reemplazar» para pedir un ítem distinto con su propio precio.")


def _resumen_item(item: RequerimientoItem) -> dict:
    return {"id_item": item.id_item, "descripcion": item.descripcion,
            "unidad_medida": item.unidad_medida, "cantidad": str(item.cantidad),
            "precio_unitario_ref": str(item.precio_unitario_ref),
            "fuente_precio": item.fuente_precio, "subtotal": str(subtotal(item))}


class ServicioAjuste:
    def __init__(self, sesion: Session, reloj: Reloj, contexto: Contexto) -> None:
        self._sesion = sesion
        self._reloj = reloj
        self._contexto = contexto
        self._validacion = ServicioValidacion(sesion, reloj, contexto)

    def aplicar(self, id_requerimiento: int, datos: AjusteEntrada,
                usuario: UsuarioActual) -> ResultadoAjuste:
        requerimiento = MaquinaEstados(self._sesion, self._reloj, self._contexto).bloquear(
            id_requerimiento, usuario)
        actual = situacion(self._sesion, requerimiento)
        if not actual.puede_aplicar_ajuste:
            raise ErrorNegocio(409, "Conflicto",
                               "El ajuste solo se aplica una vez sobre la última validación en "
                               "rojo de un requerimiento en Registrado.")
        momento = self._reloj()
        detalle: dict = {"opcion": datos.opcion}
        ajuste = AjusteRequerimiento(id_validacion=actual.validacion.id_validacion,
                                     opcion=datos.opcion, fecha_hora=momento)
        if datos.opcion == "REFORMULAR":
            detalle |= self._reformular(requerimiento, datos.items or [])
            ajuste.monto_nuevo = requerimiento.monto_estimado
        elif datos.opcion == "REPROGRAMAR":
            detalle |= self._reprogramar(requerimiento, datos.fecha_necesidad_nueva, momento)
            ajuste.fecha_necesidad_nueva = requerimiento.fecha_necesidad
        self._sesion.add(ajuste)
        self._sesion.flush()
        bitacora.registrar(
            self._sesion, momento, self._contexto, "AJUSTE_REQUERIMIENTO", "EXITO",
            id_usuario=usuario.id_usuario, id_rol=usuario.id_rol,
            recurso_tipo="REQUERIMIENTO", recurso_id=requerimiento.id_requerimiento,
            detalle=detalle)

        resultado = None
        if datos.opcion != "NINGUNA":
            resultado = self._validacion.revalidar(requerimiento, usuario, momento)
        self._sesion.commit()
        nueva = situacion(self._sesion, requerimiento)
        return ResultadoAjuste(
            requerimiento_id=requerimiento.id_requerimiento, codigo=requerimiento.codigo,
            opcion=datos.opcion, monto_estimado=requerimiento.monto_estimado,
            fecha_necesidad=requerimiento.fecha_necesidad, revalidado=resultado is not None,
            estado_semaforo=str(resultado.estado) if resultado else None,
            motivo=str(resultado.motivo) if resultado else None,
            semaforo_vigente=str(nueva.vigente))

    # --- Reformular ----------------------------------------------------------------------
    def _reformular(self, requerimiento: Requerimiento, items: list[ItemAjuste]) -> dict:
        if not items:
            raise DatosNoValidos("Reformular exige al menos un ítem.")
        originales = {i.id_item: i for i in requerimiento.items}
        anteriores = [_resumen_item(i) for i in requerimiento.items]
        monto_anterior = requerimiento.monto_estimado

        conservados = [i for i in items if i.id_item_original is not None]
        nuevos = [i for i in items if i.id_item_original is None]
        self._verificar_entradas(originales, conservados, nuevos)
        ids = [i.id_item_original for i in conservados]

        # Se aplican los cambios: cantidades, ítems quitados e ítems nuevos.
        for entrada in conservados:
            originales[entrada.id_item_original].cantidad = entrada.cantidad
        quitados = set(originales) - set(ids)
        for id_item in quitados:
            item = originales[id_item]
            requerimiento.items.remove(item)
            self._sesion.delete(item)
        for entrada in nuevos:
            requerimiento.items.append(RequerimientoItem(
                id_requerimiento=requerimiento.id_requerimiento,
                descripcion=entrada.descripcion, unidad_medida=entrada.unidad_medida,
                cantidad=entrada.cantidad, precio_unitario_ref=entrada.precio_unitario_ref,
                fuente_precio=entrada.fuente_precio))
        monto = calcular_monto_estimado(requerimiento.items)
        _, parametros = self._validacion.regla_vigente()
        verificar_tope_8_uit(monto, parametros.tope_8_uit)
        requerimiento.monto_estimado = monto
        # Lo que se pide cambió: el Área Usuaria revisa el paso 2 y vuelve a enviar.
        requerimiento.fecha_envio = None
        self._sesion.flush()
        return {"monto_anterior": str(monto_anterior), "monto_nuevo": str(monto),
                "items_anteriores": anteriores,
                "items_nuevos": [_resumen_item(i) for i in requerimiento.items]}

    def _verificar_entradas(
        self, originales: dict[int, RequerimientoItem], conservados: list[ItemAjuste],
        nuevos: list[ItemAjuste],
    ) -> None:
        ids = [i.id_item_original for i in conservados]
        if len(ids) != len(set(ids)):
            raise DatosNoValidos("Un ítem del requerimiento aparece más de una vez.")
        for entrada in conservados:
            original = originales.get(entrada.id_item_original)
            if original is None:
                raise DatosNoValidos(
                    f"El ítem {entrada.id_item_original} no pertenece al requerimiento.")
            self._verificar_conservado(entrada, original)
        for numero, entrada in enumerate(nuevos, start=1):
            faltan = [campo for campo in ("descripcion", "unidad_medida",
                                          "precio_unitario_ref", "fuente_precio")
                      if getattr(entrada, campo) is None]
            if faltan:
                raise DatosNoValidos(f"El ítem nuevo {numero} debe indicar descripción, "
                                     "unidad, precio unitario y fuente del precio.")
        sin_cambios = (not nuevos and len(conservados) == len(originales) and all(
            e.cantidad == originales[e.id_item_original].cantidad for e in conservados))
        if sin_cambios:
            raise DatosNoValidos("La reformulación no cambia el requerimiento: reduzca una "
                                 "cantidad, quite un ítem o reemplácelo.")

    @staticmethod
    def _verificar_conservado(entrada: ItemAjuste, original: RequerimientoItem) -> None:
        if entrada.precio_unitario_ref is not None and (
                entrada.precio_unitario_ref != original.precio_unitario_ref):
            raise DatosNoValidos(MENSAJE_RI26)
        cambia_descripcion = entrada.descripcion is not None and (
            entrada.descripcion != original.descripcion)
        cambia_unidad = entrada.unidad_medida is not None and (
            entrada.unidad_medida != original.unidad_medida)
        if cambia_descripcion or cambia_unidad:
            raise DatosNoValidos("Para pedir un ítem distinto use «Reemplazar»: el ítem que se "
                                 "conserva mantiene su descripción y su unidad.")
        if entrada.cantidad > original.cantidad:
            raise DatosNoValidos(
                f"La cantidad de «{original.descripcion}» solo puede reducirse "
                f"(máximo {original.cantidad.normalize():f}).")

    # --- Reprogramar ---------------------------------------------------------------------
    @staticmethod
    def _reprogramar(requerimiento: Requerimiento, nueva: date | None,
                     momento: datetime) -> dict:
        if nueva is None:
            raise DatosNoValidos("Reprogramar exige la nueva fecha de necesidad.")
        if nueva < fecha_local(momento):
            raise DatosNoValidos("La nueva fecha de necesidad no puede ser anterior a hoy.")
        if nueva <= requerimiento.fecha_necesidad:
            raise DatosNoValidos("La nueva fecha de necesidad debe ser posterior a la actual "
                                 f"({requerimiento.fecha_necesidad:%d/%m/%Y}).")
        anterior = requerimiento.fecha_necesidad
        requerimiento.fecha_necesidad = nueva
        return {"fecha_anterior": anterior.isoformat(), "fecha_nueva": nueva.isoformat()}

