"""Acceso a requerimientos, ítems, validaciones e historial de etapas."""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modelos.requerimiento import (
    AjusteRequerimiento,
    DecisionPresupuesto,
    HistorialEtapa,
    Requerimiento,
    ValidacionPresupuestal,
)


class RepositorioRequerimientos:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def siguiente_codigo(self, anio: int) -> str:
        """Código correlativo visible para el usuario, por ejemplo REQ-2026-00012."""
        numero = self._sesion.scalar(text("SELECT nextval('seq_codigo_requerimiento')"))
        return f"REQ-{anio}-{numero:05d}"

    def agregar(self, *registros: object) -> None:
        self._sesion.add_all(registros)
        self._sesion.flush()

    def obtener(self, id_requerimiento: int) -> Requerimiento | None:
        return self._sesion.get(Requerimiento, id_requerimiento)

    def ultima_validacion(self, id_requerimiento: int) -> ValidacionPresupuestal | None:
        """Semáforo vigente: la validación más reciente (índice I-05)."""
        return self._sesion.scalar(
            select(ValidacionPresupuestal)
            .where(ValidacionPresupuestal.id_requerimiento == id_requerimiento)
            .order_by(ValidacionPresupuestal.fecha_hora.desc(),
                      ValidacionPresupuestal.id_validacion.desc())
            .limit(1)
        )

    def decision(self, id_validacion: int) -> DecisionPresupuesto | None:
        """Decisión de Presupuesto sobre una validación en ámbar (relación 1:1, R16)."""
        return self._sesion.scalar(
            select(DecisionPresupuesto).where(DecisionPresupuesto.id_validacion == id_validacion)
        )

    def ajuste(self, id_validacion: int) -> AjusteRequerimiento | None:
        """Ajuste aplicado a una validación en rojo (relación 1:1, R15)."""
        return self._sesion.scalar(
            select(AjusteRequerimiento).where(AjusteRequerimiento.id_validacion == id_validacion)
        )

    def historial(self, id_requerimiento: int) -> list[HistorialEtapa]:
        return list(self._sesion.scalars(
            select(HistorialEtapa)
            .where(HistorialEtapa.id_requerimiento == id_requerimiento)
            .order_by(HistorialEtapa.fecha_hora, HistorialEtapa.id_historial)
        ))
