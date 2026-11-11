"""Datos de la pantalla Inicio (P02): fecha de corte, resumen y «Pendientes de su acción».

La lista de pendientes se deriva del estado actual de cada requerimiento; no se guardan
notificaciones (cambio 6 de la Tabla 26 de la Práctica 7). Cada rol funcional ve su propia
lista con el mismo patrón (H4): el Área Usuaria, lo que debe ajustar, subsanar, completar o
anular; la Gerencia de Administración, su bandeja de aprobación (P08); y el Jefe de
Presupuesto, los ámbar sin decisión (P11). La lista del Jefe de Logística llega con sus
pantallas (P09, P10 y P13).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.reloj import fecha_local
from app.esquemas.inicio import InicioSalida, PendienteSalida, TarjetasSalida
from app.repositorios.presupuesto import RepositorioPresupuesto
from app.seguridad.dependencias import UsuarioActual
from app.servicios.validacion.listas import accion_area_usuaria
from app.servicios.validacion.situacion import Situacion, situaciones_abiertas
from app.servicios.validacion.vigencia import SemaforoVigente

MOTIVOS_AMBAR = {
    "SIN_DATOS_META": "La meta no tiene saldo en la base presupuestal",
    "DATO_DESACTUALIZADO": "El dato presupuestal está desactualizado",
    "NO_PREVISTO_PAC": "No está previsto en el PAC",
}


def construir_inicio(sesion: Session, usuario: UsuarioActual, ahora: datetime) -> InicioSalida:
    presupuesto = RepositorioPresupuesto(sesion)
    anio = fecha_local(ahora).year
    mef = presupuesto.ultima_carga_exitosa("MEF", anio)
    seace = presupuesto.ultima_carga_exitosa("SEACE", anio)
    salida = InicioSalida(fecha_corte_mef=mef.fecha_corte if mef else None,
                          fecha_corte_seace=seace.fecha_corte if seace else None,
                          tarjetas=None, pendientes=[], pendientes_disponibles=False)
    if usuario.codigo_rol == "AU" and usuario.id_unidad is not None:
        _inicio_area_usuaria(sesion, usuario.id_unidad, ahora, salida)
    elif usuario.codigo_rol == "GA":
        salida.pendientes = [
            _fila(s, "Verde · Confirmado por Presupuesto" if s.confirmado_por_presupuesto
                  else "Verde", "Enviado por el Área Usuaria", "Aprobar u observar",
                  f"/bandeja?id={s.requerimiento.id_requerimiento}", s.inicio_del_plazo())
            for s in situaciones_abiertas(sesion) if s.en_bandeja_de_gerencia]
        salida.pendientes_disponibles = True
    elif usuario.codigo_rol == "JP":
        salida.pendientes = [
            _fila(s, "Ámbar", MOTIVOS_AMBAR.get(s.validacion.motivo, s.validacion.motivo),
                  "Confirmar o denegar", f"/alertas?id={s.requerimiento.id_requerimiento}",
                  s.validacion.fecha_hora)
            for s in situaciones_abiertas(sesion) if s.ambar_sin_decision]
        salida.pendientes_disponibles = True
    salida.pendientes.sort(key=lambda p: p.desde)  # el más antiguo primero
    return salida


def _fila(s: Situacion, situacion_texto: str, motivo: str, accion: str, destino: str,
          desde: datetime | None) -> PendienteSalida:
    req = s.requerimiento
    return PendienteSalida(
        requerimiento_id=req.id_requerimiento, codigo=req.codigo, descripcion=req.descripcion,
        situacion=situacion_texto, motivo=motivo, desde=desde or s.desde, accion=accion,
        destino=destino)


def _inicio_area_usuaria(sesion: Session, id_unidad: int, ahora: datetime,
                         salida: InicioSalida) -> None:
    tarjetas = TarjetasSalida(verde=0, ambar=0, rojo=0, observado=0, cuello_de_botella=0)
    for s in situaciones_abiertas(sesion, id_unidad):
        if s.codigo_estado == "OBSERVADO":  # los observados no se cuentan por color (H7)
            tarjetas.observado += 1
        elif s.vigente == SemaforoVigente.VERDE:
            tarjetas.verde += 1
        elif s.vigente == SemaforoVigente.ROJO:
            tarjetas.rojo += 1
        else:
            tarjetas.ambar += 1
        if s.excedido(ahora):
            tarjetas.cuello_de_botella += 1
        pendiente = accion_area_usuaria(s)
        if pendiente:
            situacion_texto, motivo, accion, destino = pendiente
            salida.pendientes.append(_fila(s, situacion_texto, motivo, accion, destino,
                                           s.desde))
    salida.tarjetas = tarjetas
    salida.pendientes_disponibles = True
