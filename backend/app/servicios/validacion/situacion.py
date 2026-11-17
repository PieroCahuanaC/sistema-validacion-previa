"""Situación actual de un requerimiento: estado, semáforo vigente, ajuste y tiempo en la etapa.

Es la base común de las listas de trabajo (P02, P08, P11, P17) y del detalle (P04): todas
derivan lo que cada rol debe hacer del estado actual, sin guardar notificaciones (cambio 6
de la Tabla 26 de la Práctica 7).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modelos.catalogos import Estado
from app.modelos.requerimiento import (
    AjusteRequerimiento,
    DecisionPresupuesto,
    HistorialEtapa,
    Requerimiento,
    ValidacionPresupuestal,
)
from app.repositorios.requerimientos import RepositorioRequerimientos
from app.servicios.validacion.vigencia import SemaforoVigente, semaforo_vigente

SITUACION_VISIBLE = {
    SemaforoVigente.VERDE: "Verde",
    SemaforoVigente.AMBAR_PENDIENTE: "Ámbar",
    SemaforoVigente.AMBAR_DENEGADO: "Ámbar",
    SemaforoVigente.ROJO: "Rojo",
}


@dataclass(frozen=True)
class Situacion:
    requerimiento: Requerimiento
    estado: Estado
    validacion: ValidacionPresupuestal
    decision: DecisionPresupuesto | None
    ajuste: AjusteRequerimiento | None
    vigente: SemaforoVigente
    desde: datetime  # ingreso a la etapa actual (para el plazo de la etapa)

    @property
    def codigo_estado(self) -> str:
        return self.estado.codigo

    @property
    def enviado(self) -> bool:
        return self.requerimiento.fecha_envio is not None

    @property
    def opcion_ajuste(self) -> str | None:
        return self.ajuste.opcion if self.ajuste else None

    @property
    def semaforo_visible(self) -> str:
        return SITUACION_VISIBLE[self.vigente]

    @property
    def confirmado_por_presupuesto(self) -> bool:
        return (self.validacion.estado_semaforo == "AMBAR" and self.decision is not None
                and self.decision.resultado == "CONFIRMADA")

    def inicio_del_plazo(self) -> datetime | None:
        """En Registrado el plazo de la Gerencia corre desde el envío (P08); antes no corre."""
        if self.codigo_estado == "REGISTRADO":
            if not self.enviado:
                return None
            return max(self.requerimiento.fecha_envio, self.desde)
        return self.desde

    def horas_en_etapa(self, ahora: datetime) -> float | None:
        inicio = self.inicio_del_plazo()
        return None if inicio is None else (ahora - inicio).total_seconds() / 3600

    def excedido(self, ahora: datetime) -> bool:
        horas = self.horas_en_etapa(ahora)
        return (self.estado.plazo_horas is not None and horas is not None
                and horas > self.estado.plazo_horas)

    # --- Qué acción le corresponde a cada rol --------------------------------------------
    @property
    def puede_aplicar_ajuste(self) -> bool:
        return (self.codigo_estado == "REGISTRADO" and self.vigente == SemaforoVigente.ROJO
                and self.ajuste is None)

    @property
    def puede_anular(self) -> bool:
        """RI-25: solo sin salida, es decir, Rojo con ajuste Ninguna o Ámbar denegado."""
        return self.codigo_estado == "REGISTRADO" and (
            (self.vigente == SemaforoVigente.ROJO and self.opcion_ajuste == "NINGUNA")
            or self.vigente == SemaforoVigente.AMBAR_DENEGADO)

    @property
    def puede_subsanar(self) -> bool:
        return self.codigo_estado == "OBSERVADO"

    @property
    def en_bandeja_de_gerencia(self) -> bool:
        return (self.codigo_estado == "REGISTRADO" and self.enviado
                and self.vigente == SemaforoVigente.VERDE)

    @property
    def ambar_sin_decision(self) -> bool:
        return not self.estado.es_final and self.vigente == SemaforoVigente.AMBAR_PENDIENTE


def situacion(sesion: Session, requerimiento: Requerimiento) -> Situacion:
    repo = RepositorioRequerimientos(sesion)
    validacion = repo.ultima_validacion(requerimiento.id_requerimiento)
    if validacion is None:
        raise RuntimeError("Todo requerimiento tiene al menos una validación (R12).")
    decision = repo.decision(validacion.id_validacion)
    ajuste = repo.ajuste(validacion.id_validacion)
    desde = sesion.scalar(
        select(HistorialEtapa.fecha_hora)
        .where(HistorialEtapa.id_requerimiento == requerimiento.id_requerimiento)
        .order_by(HistorialEtapa.fecha_hora.desc(), HistorialEtapa.id_historial.desc())
        .limit(1))
    return Situacion(
        requerimiento=requerimiento, estado=sesion.get(Estado, requerimiento.id_estado_actual),
        validacion=validacion, decision=decision, ajuste=ajuste,
        vigente=semaforo_vigente(validacion.estado_semaforo,
                                 decision.resultado if decision else None),
        desde=desde or requerimiento.fecha_registro,
    )


def situaciones_en_lote(sesion: Session, requerimientos: list[Requerimiento]) -> list[Situacion]:
    """Situación de varios requerimientos con un número fijo de consultas, en el mismo orden.

    Equivale a llamar a situacion() por cada uno, pero las listas (P02, P06, P08, P11, P17)
    no crecen en consultas con el número de requerimientos (RNF de rendimiento).
    """
    if not requerimientos:
        return []
    ids = [r.id_requerimiento for r in requerimientos]
    ultimas = (select(ValidacionPresupuestal)
               .where(ValidacionPresupuestal.id_requerimiento.in_(ids))
               .distinct(ValidacionPresupuestal.id_requerimiento)
               .order_by(ValidacionPresupuestal.id_requerimiento,
                         ValidacionPresupuestal.fecha_hora.desc(),
                         ValidacionPresupuestal.id_validacion.desc()))
    validaciones = {v.id_requerimiento: v for v in sesion.scalars(ultimas)}
    ids_validacion = [v.id_validacion for v in validaciones.values()]
    decisiones = {d.id_validacion: d for d in sesion.scalars(
        select(DecisionPresupuesto).where(DecisionPresupuesto.id_validacion.in_(ids_validacion)))}
    ajustes = {a.id_validacion: a for a in sesion.scalars(
        select(AjusteRequerimiento).where(AjusteRequerimiento.id_validacion.in_(ids_validacion)))}
    desde = dict(sesion.execute(
        select(HistorialEtapa.id_requerimiento, func.max(HistorialEtapa.fecha_hora))
        .where(HistorialEtapa.id_requerimiento.in_(ids))
        .group_by(HistorialEtapa.id_requerimiento)).tuples().all())
    estados = {e.id_estado: e for e in sesion.scalars(select(Estado))}

    resultado = []
    for req in requerimientos:
        validacion = validaciones.get(req.id_requerimiento)
        if validacion is None:
            raise RuntimeError("Todo requerimiento tiene al menos una validación (R12).")
        decision = decisiones.get(validacion.id_validacion)
        resultado.append(Situacion(
            requerimiento=req, estado=estados[req.id_estado_actual], validacion=validacion,
            decision=decision, ajuste=ajustes.get(validacion.id_validacion),
            vigente=semaforo_vigente(validacion.estado_semaforo,
                                     decision.resultado if decision else None),
            desde=desde.get(req.id_requerimiento) or req.fecha_registro,
        ))
    return resultado


def situaciones_abiertas(sesion: Session, id_unidad: int | None = None) -> list[Situacion]:
    """Requerimientos no cerrados (de una unidad, si se indica), del más antiguo al más nuevo."""
    consulta = (select(Requerimiento)
                .join(Estado, Estado.id_estado == Requerimiento.id_estado_actual)
                .where(Estado.es_final.is_(False)).order_by(Requerimiento.fecha_registro))
    if id_unidad is not None:
        consulta = consulta.where(Requerimiento.id_unidad == id_unidad)
    return situaciones_en_lote(sesion, list(sesion.scalars(consulta)))


def horas_a_texto(horas: float | None) -> str:
    if horas is None:
        return "—"
    if 0 <= horas < 1:  # igual que en la interfaz: un trámite recién movido no muestra «0 h»
        return "menos de 1 h"
    total = timedelta(hours=horas)
    dias, resto = divmod(int(total.total_seconds()) // 3600, 24)
    return f"{dias} d {resto} h" if dias else f"{resto} h"
