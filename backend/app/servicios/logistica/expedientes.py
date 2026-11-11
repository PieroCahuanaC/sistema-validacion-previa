"""Listas de trabajo de Logística (P09, P10, P13) y de Presupuesto (P12), y sus pendientes
en la P02. Se derivan del estado actual de cada requerimiento."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import ErrorNegocio
from app.esquemas.logistica import ExpedienteFila
from app.modelos.catalogos import UnidadOrganica
from app.modelos.presupuesto import MetaPresupuestal
from app.servicios.logistica.cuadro import cuadro_de, devolucion_de_presupuesto
from app.servicios.validacion.situacion import Situacion, situaciones_abiertas
from app.servicios.validacion.vigencia import SemaforoVigente

# Estados que cada rol trabaja desde sus pantallas, con la acción y la pantalla que la abre.
ACCIONES = {
    "JL": {
        "APROBADO": ("Validar documentos", "/validacion"),
        "DOCUMENTACION_VALIDADA": ("Registrar cuadro comparativo", "/cuadro"),
        "CERTIFICADO": ("Registrar orden y compromiso", "/orden"),
    },
    "JP": {
        "CUADRO_REGISTRADO": ("Registrar certificación", "/certificacion"),
    },
}


def _nota(sesion: Session, s: Situacion) -> tuple[bool, str | None]:
    if s.codigo_estado == "DOCUMENTACION_VALIDADA":
        devolucion = devolucion_de_presupuesto(sesion, s.requerimiento)
        if devolucion is not None:
            return True, f"Devuelto por Presupuesto: {devolucion}"
        if cuadro_de(sesion, s.requerimiento.id_requerimiento) is not None:
            return False, "Vuelve tras un ajuste: corrija el cuadro con precios vigentes"
    if s.codigo_estado == "CUADRO_REGISTRADO":
        if s.vigente == SemaforoVigente.AMBAR_PENDIENTE:
            return False, "Ámbar con el precio de mercado: decida antes en el Panel de alertas"
        if s.vigente == SemaforoVigente.AMBAR_DENEGADO:
            return False, "Disponibilidad denegada: anule por falta de disponibilidad"
    return False, None


def accion_pendiente(sesion: Session, s: Situacion, codigo_rol: str) -> tuple[str, str] | None:
    """(acción, destino) si el requerimiento espera a Logística o a Presupuesto."""
    accion = ACCIONES.get(codigo_rol, {}).get(s.codigo_estado)
    if accion is None:
        return None
    texto, ruta = accion
    if s.codigo_estado == "DOCUMENTACION_VALIDADA" and cuadro_de(
            sesion, s.requerimiento.id_requerimiento) is not None:
        texto = "Corregir cuadro comparativo"
    if s.codigo_estado == "CUADRO_REGISTRADO" and s.vigente == SemaforoVigente.AMBAR_DENEGADO:
        texto = "Anular por falta de disponibilidad"
    return texto, f"{ruta}?id={s.requerimiento.id_requerimiento}"


def listar_expedientes(sesion: Session, codigo_rol: str, estado: str,
                       ahora: datetime) -> list[ExpedienteFila]:
    if estado not in ACCIONES.get(codigo_rol, {}):
        raise ErrorNegocio(403, "Acceso denegado", "Su rol no trabaja expedientes en ese estado.")
    unidades = {u.id_unidad: u for u in sesion.scalars(select(UnidadOrganica))}
    metas = {m.id_meta: m for m in sesion.scalars(select(MetaPresupuestal))}
    filas = []
    for s in situaciones_abiertas(sesion):
        if s.codigo_estado != estado:
            continue
        req = s.requerimiento
        cuadro = cuadro_de(sesion, req.id_requerimiento)
        devuelto, nota = _nota(sesion, s)
        filas.append(ExpedienteFila(
            requerimiento_id=req.id_requerimiento, codigo=req.codigo,
            descripcion=req.descripcion, unidad_sigla=unidades[req.id_unidad].sigla or "—",
            meta_codigo=metas[req.id_meta].codigo, objeto_contratacion=req.objeto_contratacion,
            monto_estimado=req.monto_estimado,
            precio_referencia=cuadro.precio_referencia if cuadro else None,
            semaforo_vigente=str(s.vigente),
            confirmado_por_presupuesto=s.confirmado_por_presupuesto,
            estado_codigo=s.codigo_estado, estado_actual=s.estado.nombre, desde=s.desde,
            horas_en_etapa=round(s.horas_en_etapa(ahora) or 0, 1),
            plazo_horas=s.estado.plazo_horas, excedido=s.excedido(ahora), devuelto=devuelto,
            nota=nota))
    return sorted(filas, key=lambda f: f.desde)  # el que más espera, primero
