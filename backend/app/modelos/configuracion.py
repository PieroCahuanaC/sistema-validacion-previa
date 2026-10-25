"""Regla del semáforo versionada (Tablas 10 y 11 de la Práctica 6; RNF-04)."""

from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class ReglaSemaforo(Base):
    __tablename__ = "regla_semaforo"

    id_regla: Mapped[int] = mapped_column(primary_key=True)
    parametros: Mapped[dict] = mapped_column(JSONB)
    vigente_desde: Mapped[datetime]
    vigente_hasta: Mapped[datetime | None]
