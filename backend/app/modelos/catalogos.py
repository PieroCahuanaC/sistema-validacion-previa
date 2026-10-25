"""Catálogos: rol, unidad orgánica, estado y transición (Tablas 6 y 9 de la Práctica 6)."""

from sqlalchemy import ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class Rol(Base):
    __tablename__ = "rol"

    id_rol: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(5))
    nombre: Mapped[str] = mapped_column(String(60))
    descripcion: Mapped[str | None] = mapped_column(String(200))


class UnidadOrganica(Base):
    __tablename__ = "unidad_organica"

    id_unidad: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    sigla: Mapped[str | None] = mapped_column(String(15))
    activa: Mapped[bool]


class Estado(Base):
    __tablename__ = "estado"

    id_estado: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(60))
    plazo_horas: Mapped[int | None] = mapped_column(SmallInteger)
    orden: Mapped[int] = mapped_column(SmallInteger)
    es_final: Mapped[bool]


class Transicion(Base):
    __tablename__ = "transicion"

    id_transicion: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    id_estado_origen: Mapped[int] = mapped_column(ForeignKey("estado.id_estado"))
    id_estado_destino: Mapped[int] = mapped_column(ForeignKey("estado.id_estado"))
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"))
    tipo: Mapped[str] = mapped_column(String(10))
