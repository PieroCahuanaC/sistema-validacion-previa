"""Historial de trazabilidad del expediente (CU-02, CU-10; RF-05 a RF-07; pantalla P07).

Línea de tiempo de solo lectura con cada estado, su fecha y hora, el rol funcional que lo
registró (nunca el nombre de la persona: solo la bitácora conserva quién lo hizo), el proveído
u observación y la duración frente al plazo de la etapa, además del tiempo hasta la
certificación y el tiempo total del trámite. Un trámite cerrado (Orden emitida o Anulado)
detiene el cómputo del tiempo (estado.es_final).
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.esquemas.tramite import EtapaFutura, HistorialSalida, RegistroHistorial
from app.modelos.catalogos import Estado, Rol
from app.modelos.presupuesto import MetaPresupuestal
from app.modelos.requerimiento import Requerimiento
from app.repositorios.requerimientos import RepositorioRequerimientos
from app.servicios.validacion.detalle import ESTADOS_DEL_RECORRIDO, responsable_actual
from app.servicios.validacion.situacion import situacion


def _horas(desde: datetime, hasta: datetime) -> float:
    return round((hasta - desde).total_seconds() / 3600, 1)


def construir_historial(sesion: Session, requerimiento: Requerimiento,
                        ahora: datetime) -> HistorialSalida:
    estados = {e.id_estado: e for e in sesion.scalars(select(Estado))}
    roles = {r.id_rol: r for r in sesion.scalars(select(Rol))}
    s = situacion(sesion, requerimiento)
    cerrado = s.estado.es_final
    historial = RepositorioRequerimientos(sesion).historial(requerimiento.id_requerimiento)

    registros = []
    for indice, registro in enumerate(historial):
        estado = estados[registro.id_estado]
        siguiente = historial[indice + 1] if indice + 1 < len(historial) else None
        en_curso = siguiente is None and not estado.es_final
        horas = None
        if siguiente is not None:
            horas = _horas(registro.fecha_hora, siguiente.fecha_hora)
        elif en_curso:
            horas = _horas(registro.fecha_hora, ahora)
        registros.append(RegistroHistorial(
            estado_codigo=estado.codigo, estado=estado.nombre, fecha_hora=registro.fecha_hora,
            rol=roles[registro.id_rol].nombre, observacion=registro.observacion,
            horas_en_etapa=horas, plazo_horas=estado.plazo_horas,
            excedio_plazo=(horas is not None and estado.plazo_horas is not None
                           and horas > estado.plazo_horas),
            en_curso=en_curso))

    alcanzados = {estados[r.id_estado].codigo for r in historial}
    futuras = [] if cerrado else [
        EtapaFutura(estado_codigo=e.codigo, estado=e.nombre)
        for codigo in ESTADOS_DEL_RECORRIDO
        for e in estados.values()
        if e.codigo == codigo and codigo not in alcanzados]

    certificacion = next((r for r in historial
                          if estados[r.id_estado].codigo == "CERTIFICADO"), None)
    cierre = historial[-1] if cerrado and historial else None
    meta = sesion.get(MetaPresupuestal, requerimiento.id_meta)
    responsable, accion = responsable_actual(sesion, s)
    return HistorialSalida(
        requerimiento_id=requerimiento.id_requerimiento, codigo=requerimiento.codigo,
        descripcion=requerimiento.descripcion, meta_codigo=meta.codigo if meta else "—",
        monto_estimado=requerimiento.monto_estimado, semaforo=s.semaforo_visible,
        semaforo_vigente=str(s.vigente), estado_actual=s.estado.nombre, cerrado=cerrado,
        responsable_actual=responsable, accion_pendiente=accion, registros=registros,
        etapas_futuras=futuras,
        horas_hasta_certificacion=(_horas(requerimiento.fecha_registro, certificacion.fecha_hora)
                                   if certificacion else None),
        horas_totales=(_horas(requerimiento.fecha_registro, cierre.fecha_hora)
                       if cierre and s.codigo_estado == "ORDEN_EMITIDA" else None),
    )
