"""Usuarios, sesiones y bitácora (Tabla 6 de la Práctica 6; RF-10, RF-15, RNF-03)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(primary_key=True)
    id_rol: Mapped[int] = mapped_column(SmallInteger, ForeignKey("rol.id_rol"))
    id_unidad: Mapped[int | None] = mapped_column(SmallInteger,
                                                  ForeignKey("unidad_organica.id_unidad"))
    nombre_usuario: Mapped[str] = mapped_column(String(30))
    nombres_apellidos: Mapped[str] = mapped_column(String(120))
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    contrasena_temporal: Mapped[bool]
    intentos_fallidos: Mapped[int] = mapped_column(SmallInteger)
    bloqueado_hasta: Mapped[datetime | None]
    estado: Mapped[str] = mapped_column(String(10))


class SesionUsuario(Base):
    """Token de renovación (8 h). Solo se guarda su resumen SHA-256 (Tabla 16 de la P5)."""

    __tablename__ = "sesion"

    id_sesion: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario"))
    hash_token: Mapped[str] = mapped_column(String(64))
    emitida_en: Mapped[datetime]
    expira_en: Mapped[datetime]
    revocada_en: Mapped[datetime | None]


class Bitacora(Base):
    """Registro de auditoría de solo inserción (RI-22), encadenado por hash."""

    __tablename__ = "bitacora"

    id_bitacora: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fecha_hora: Mapped[datetime]
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("usuario.id_usuario"))
    id_rol: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("rol.id_rol"))
    actor_servicio: Mapped[str | None] = mapped_column(String(30))
    accion: Mapped[str] = mapped_column(String(30))
    recurso_tipo: Mapped[str | None] = mapped_column(String(20))
    recurso_id: Mapped[int | None] = mapped_column(BigInteger)
    resultado: Mapped[str] = mapped_column(String(10))
    detalle: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip_origen: Mapped[str | None] = mapped_column(INET)
    id_traza: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    hash_anterior: Mapped[str | None] = mapped_column(String(64))
