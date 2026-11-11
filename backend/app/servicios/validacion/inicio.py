"""Datos de la pantalla Inicio (P02): fecha de corte, resumen y «Pendientes de su acción».

La lista de pendientes se deriva del estado actual de cada requerimiento; no se guardan
notificaciones (cambio 6 de la Tabla 26 de la Práctica 7). En este incremento la calcula el
Área Usuaria; las listas de los demás roles llegan con sus pantallas (P08 a P13).
"""

from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.reloj import fecha_local
from app.esquemas.inicio import InicioSalida, PendienteSalida, TarjetasSalida
from app.modelos.catalogos import Estado
from app.modelos.requerimiento import HistorialEtapa, Requerimiento
from app.repositorios.presupuesto import RepositorioPresupuesto
from app.repositorios.requerimientos import RepositorioRequerimientos
from app.seguridad.dependencias import UsuarioActual
from app.servicios.validacion.vigencia import SemaforoVigente, semaforo_vigente


def _pendiente(req: Requerimiento, vigente: SemaforoVigente, observado: bool,
               opcion_ajuste: str | None) -> tuple[str, str, str, str] | None:
    """(situación, motivo, acción, destino) si el requerimiento espera al Área Usuaria."""
    detalle = f"/requerimientos/detalle?id={req.id_requerimiento}"
    if observado:
        return "Observado", "Devuelto con observaciones", "Revisar y subsanar", detalle
    if vigente == SemaforoVigente.ROJO and opcion_ajuste is None:
        return "Rojo", "Presupuesto insuficiente", "Aplicar ajuste", detalle
    if vigente == SemaforoVigente.ROJO:
        return "Rojo", "Sin salida: no se aceptó ninguna opción de ajuste", "Revisar y anular", \
            detalle
    if vigente == SemaforoVigente.AMBAR_DENEGADO:
        return "Ámbar", "Sin salida: Presupuesto denegó la disponibilidad", "Revisar y anular", \
            detalle
    if vigente == SemaforoVigente.VERDE and req.fecha_envio is None:
        return "Verde", "Complete el paso 2 y envíe a la Gerencia", "Completar paso 2", \
            f"/requerimientos/nuevo?id={req.id_requerimiento}"
    return None


def construir_inicio(sesion: Session, usuario: UsuarioActual, ahora: datetime) -> InicioSalida:
    presupuesto = RepositorioPresupuesto(sesion)
    anio = fecha_local(ahora).year
    mef = presupuesto.ultima_carga_exitosa("MEF", anio)
    seace = presupuesto.ultima_carga_exitosa("SEACE", anio)
    salida = InicioSalida(fecha_corte_mef=mef.fecha_corte if mef else None,
                          fecha_corte_seace=seace.fecha_corte if seace else None,
                          tarjetas=None, pendientes=[], pendientes_disponibles=False)
    if usuario.codigo_rol != "AU" or usuario.id_unidad is None:
        return salida

    repo = RepositorioRequerimientos(sesion)
    estados = {e.id_estado: e for e in sesion.scalars(select(Estado))}
    tarjetas = TarjetasSalida(verde=0, ambar=0, rojo=0, observado=0, cuello_de_botella=0)
    pendientes: list[PendienteSalida] = []
    abiertos = sesion.scalars(select(Requerimiento).where(
        Requerimiento.id_unidad == usuario.id_unidad).order_by(Requerimiento.fecha_registro))
    for req in abiertos:
        estado = estados[req.id_estado_actual]
        if estado.es_final:
            continue
        validacion = repo.ultima_validacion(req.id_requerimiento)
        decision = repo.decision(validacion.id_validacion) if validacion else None
        vigente = semaforo_vigente(validacion.estado_semaforo if validacion else "AMBAR",
                                   decision.resultado if decision else None)
        observado = estado.codigo == "OBSERVADO"
        if observado:  # los observados no se cuentan en las tarjetas de color (H7)
            tarjetas.observado += 1
        elif vigente == SemaforoVigente.VERDE:
            tarjetas.verde += 1
        elif vigente == SemaforoVigente.ROJO:
            tarjetas.rojo += 1
        else:
            tarjetas.ambar += 1
        desde = _inicio_de_etapa(sesion, req)
        if _es_cuello_de_botella(estado, req, desde, ahora):
            tarjetas.cuello_de_botella += 1
        opcion = sesion.scalar(text(
            "SELECT opcion FROM ajuste_requerimiento WHERE id_validacion = :v"),
            {"v": validacion.id_validacion}) if validacion else None
        pendiente = _pendiente(req, vigente, observado, opcion)
        if pendiente:
            situacion, motivo, accion, destino = pendiente
            pendientes.append(PendienteSalida(
                requerimiento_id=req.id_requerimiento, codigo=req.codigo,
                descripcion=req.descripcion, situacion=situacion, motivo=motivo,
                desde=desde, accion=accion, destino=destino))
    salida.tarjetas = tarjetas
    salida.pendientes = sorted(pendientes, key=lambda p: p.desde)  # el más antiguo primero
    salida.pendientes_disponibles = True
    return salida


def _inicio_de_etapa(sesion: Session, req: Requerimiento) -> datetime:
    ultimo = sesion.scalar(select(HistorialEtapa.fecha_hora)
                           .where(HistorialEtapa.id_requerimiento == req.id_requerimiento)
                           .order_by(HistorialEtapa.fecha_hora.desc()).limit(1))
    return ultimo or req.fecha_registro


def _es_cuello_de_botella(estado: Estado, req: Requerimiento, desde: datetime,
                          ahora: datetime) -> bool:
    """Supera el plazo de su etapa; en Registrado el plazo corre desde el envío (P08)."""
    if estado.plazo_horas is None:
        return False
    if estado.codigo == "REGISTRADO":
        if req.fecha_envio is None:
            return False
        desde = req.fecha_envio
    return ahora - desde > timedelta(hours=estado.plazo_horas)
