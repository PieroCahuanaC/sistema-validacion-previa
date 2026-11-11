"""Revisión documental, proveedores, cuadro comparativo y cotizaciones (Tabla 10 de la
Práctica 6; CU-07 y CU-08)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modelos.base import Base


class TipoDocumento(Base):
    __tablename__ = "tipo_documento"

    id_tipo_documento: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    obligatorio: Mapped[bool]
    activo: Mapped[bool]


class RevisionDocumento(Base):
    __tablename__ = "revision_documento"

    id_revision: Mapped[int] = mapped_column(primary_key=True)
    id_requerimiento: Mapped[int] = mapped_column(ForeignKey("requerimiento.id_requerimiento"))
    id_tipo_documento: Mapped[int] = mapped_column(ForeignKey("tipo_documento.id_tipo_documento"))
    resultado: Mapped[str] = mapped_column(String(10))
    observacion: Mapped[str | None] = mapped_column(String(500))
    fecha_hora: Mapped[datetime]


class Proveedor(Base):
    """El RUC y la razón social de una persona natural se guardan cifrados (Ley N.° 29733)."""

    __tablename__ = "proveedor"

    id_proveedor: Mapped[int] = mapped_column(primary_key=True)
    tipo_persona: Mapped[str] = mapped_column(String(10))
    ruc: Mapped[str] = mapped_column(String(255))
    ruc_hash: Mapped[str] = mapped_column(String(64))
    razon_social: Mapped[str] = mapped_column(String(500))


class CuadroComparativo(Base):
    __tablename__ = "cuadro_comparativo"

    id_cuadro: Mapped[int] = mapped_column(primary_key=True)
    id_requerimiento: Mapped[int] = mapped_column(ForeignKey("requerimiento.id_requerimiento"))
    fecha_registro: Mapped[datetime]
    precio_referencia: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    observacion: Mapped[str | None] = mapped_column(String(500))

    cotizaciones: Mapped[list["Cotizacion"]] = relationship(
        order_by="Cotizacion.id_cotizacion", lazy="selectin", cascade="all, delete-orphan")


class Cotizacion(Base):
    __tablename__ = "cotizacion"

    id_cotizacion: Mapped[int] = mapped_column(primary_key=True)
    id_cuadro: Mapped[int] = mapped_column(ForeignKey("cuadro_comparativo.id_cuadro"))
    id_proveedor: Mapped[int] = mapped_column(ForeignKey("proveedor.id_proveedor"))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha_cotizacion: Mapped[date]
