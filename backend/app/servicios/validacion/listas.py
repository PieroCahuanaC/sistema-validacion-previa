"""Listas de trabajo por rol: P17 (Área Usuaria), P08 (Gerencia) y P11 (Presupuesto), y la
acción pendiente de cada requerimiento que alimenta «Pendientes de su acción» de la P02.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.esquemas.tramite import AlertaSalida, AlertasSalida, BandejaFila, MiRequerimientoFila
from app.modelos.catalogos import Estado, UnidadOrganica
from app.modelos.presupuesto import CargaDatos, MetaPresupuestal, SaldoMeta
from app.modelos.requerimiento import Requerimiento
from app.servicios.validacion.situacion import Situacion, situacion, situaciones_abiertas
from app.servicios.validacion.vigencia import SemaforoVigente


def detalle_url(id_requerimiento: int) -> str:
    return f"/requerimientos/detalle?id={id_requerimiento}"


def accion_area_usuaria(s: Situacion) -> tuple[str, str, str, str] | None:
    """(situación, motivo, acción, destino) si el requerimiento espera al Área Usuaria."""
    rid = s.requerimiento.id_requerimiento
    if s.puede_subsanar:
        return "Observado", "Devuelto con observaciones", "Revisar y subsanar", detalle_url(rid)
    if s.codigo_estado != "REGISTRADO":
        return None
    if s.puede_aplicar_ajuste:
        return "Rojo", "Presupuesto insuficiente", "Aplicar ajuste", \
            f"/requerimientos/ajuste?id={rid}"
    if s.vigente == SemaforoVigente.ROJO and s.opcion_ajuste == "NINGUNA":
        return "Rojo", "Sin salida: no se aceptó ninguna opción de ajuste", "Revisar y anular", \
            detalle_url(rid)
    if s.vigente == SemaforoVigente.AMBAR_DENEGADO:
        return "Ámbar", "Sin salida: Presupuesto denegó la disponibilidad", "Revisar y anular", \
            detalle_url(rid)
    if s.vigente == SemaforoVigente.VERDE and not s.enviado:
        return "Verde", "Complete el paso 2 y envíe a la Gerencia", "Completar paso 2", \
            f"/requerimientos/nuevo?id={rid}"
    return None


# --- P17. Mis requerimientos ---------------------------------------------------------------
def mis_requerimientos(
    sesion: Session, id_unidad: int, semaforo: str | None, estado: str | None,
    buscar: str | None, cuello_de_botella: bool = False, ahora: datetime | None = None,
) -> list[MiRequerimientoFila]:
    consulta = (select(Requerimiento).where(Requerimiento.id_unidad == id_unidad)
                .order_by(Requerimiento.fecha_registro.desc()))
    if estado:
        consulta = consulta.join(Estado, Estado.id_estado == Requerimiento.id_estado_actual) \
            .where(Estado.codigo == estado)
    if buscar:
        consulta = consulta.where(Requerimiento.codigo.ilike(f"%{buscar.strip()}%"))
    metas = {m.id_meta: m.codigo for m in sesion.scalars(select(MetaPresupuestal))}
    filas = []
    for req in sesion.scalars(consulta):
        s = situacion(sesion, req)
        if semaforo and (s.codigo_estado == "OBSERVADO" or not s.vigente.startswith(semaforo)):
            continue  # como en las tarjetas de la P02, los observados no se cuentan por color
        if cuello_de_botella and not (ahora and not s.estado.es_final and s.excedido(ahora)):
            continue
        pendiente = accion_area_usuaria(s)
        filas.append(MiRequerimientoFila(
            requerimiento_id=req.id_requerimiento, codigo=req.codigo,
            descripcion=req.descripcion, meta_codigo=metas.get(req.id_meta, "—"),
            monto_estimado=req.monto_estimado, semaforo=s.semaforo_visible,
            semaforo_vigente=str(s.vigente), estado_codigo=s.codigo_estado,
            estado_actual=s.estado.nombre, fecha_necesidad=req.fecha_necesidad,
            fecha_registro=req.fecha_registro, accion=pendiente[2] if pendiente else None,
            destino=pendiente[3] if pendiente else detalle_url(req.id_requerimiento)))
    return filas


# --- P08. Bandeja de aprobación -----------------------------------------------------------
def bandeja_gerencia(sesion: Session, ahora: datetime) -> list[BandejaFila]:
    unidades = {u.id_unidad: u for u in sesion.scalars(select(UnidadOrganica))}
    metas = {m.id_meta: m for m in sesion.scalars(select(MetaPresupuestal))}
    filas = []
    for s in situaciones_abiertas(sesion):
        if not s.en_bandeja_de_gerencia:
            continue
        req = s.requerimiento
        unidad, meta = unidades[req.id_unidad], metas[req.id_meta]
        filas.append(BandejaFila(
            requerimiento_id=req.id_requerimiento, codigo=req.codigo,
            descripcion=req.descripcion, unidad_sigla=unidad.sigla or "—",
            unidad_nombre=unidad.nombre, meta_codigo=meta.codigo, meta_nombre=meta.nombre,
            objeto_contratacion=req.objeto_contratacion, monto_estimado=req.monto_estimado,
            fecha_necesidad=req.fecha_necesidad, semaforo=s.semaforo_visible,
            confirmado_por_presupuesto=s.confirmado_por_presupuesto,
            motivo=s.validacion.motivo, fecha_validacion=s.validacion.fecha_hora,
            fecha_envio=req.fecha_envio, horas_en_bandeja=round(s.horas_en_etapa(ahora), 1),
            plazo_horas=s.estado.plazo_horas, excedido=s.excedido(ahora)))
    return sorted(filas, key=lambda f: -f.horas_en_bandeja)  # el que más espera, primero


# --- P11. Panel de alertas ----------------------------------------------------------------
def alertas_presupuesto(sesion: Session, ahora: datetime) -> AlertasSalida:
    unidades = {u.id_unidad: u for u in sesion.scalars(select(UnidadOrganica))}
    metas = {m.id_meta: m for m in sesion.scalars(select(MetaPresupuestal))}
    ambar, rojo = [], []
    for s in situaciones_abiertas(sesion):
        if s.ambar_sin_decision:
            ambar.append(_alerta(sesion, s, unidades, metas, ahora))
        elif s.vigente == SemaforoVigente.ROJO:
            rojo.append(_alerta(sesion, s, unidades, metas, ahora))
    orden = lambda a: a.fecha_validacion  # noqa: E731 - la alerta más antigua primero
    return AlertasSalida(ambar=sorted(ambar, key=orden), rojo=sorted(rojo, key=orden))


def _alerta(sesion: Session, s: Situacion, unidades: dict, metas: dict,
            ahora: datetime) -> AlertaSalida:
    req, validacion = s.requerimiento, s.validacion
    fecha_corte = None
    if validacion.id_saldo is not None:
        saldo = sesion.get(SaldoMeta, validacion.id_saldo)
        carga = sesion.get(CargaDatos, saldo.id_carga) if saldo else None
        fecha_corte = carga.fecha_corte if carga else None
    return AlertaSalida(
        requerimiento_id=req.id_requerimiento, codigo=req.codigo, descripcion=req.descripcion,
        unidad_sigla=unidades[req.id_unidad].sigla or "—",
        meta_codigo=metas[req.id_meta].codigo, monto_evaluado=validacion.monto_evaluado,
        motivo=validacion.motivo, fecha_corte=fecha_corte,
        fecha_validacion=validacion.fecha_hora,
        dias_en_alerta=max(0, (ahora - validacion.fecha_hora).days),
        estado_actual=s.estado.nombre, opcion_ajuste=s.opcion_ajuste)
