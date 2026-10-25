"""Base presupuestal y PAC: carga, meta, saldo e ítem del PAC (Tabla 7 de la Práctica 6)."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base


class CargaDatos(Base):
    __tablename__ = "carga_datos"

    id_carga: Mapped[int] = mapped_column(primary_key=True)
    fuente: Mapped[str] = mapped_column(String(10))
    origen: Mapped[str] = mapped_column(String(12))
    anio_fiscal: Mapped[int] = mapped_column(SmallInteger)
    fecha_ejecucion: Mapped[datetime]
    fecha_corte: Mapped[datetime | None]
    resultado: Mapped[str] = mapped_column(String(10))
    detalle_error: Mapped[str | None] = mapped_column(String(500))


class MetaPresupuestal(Base):
    __tablename__ = "meta_presupuestal"

    id_meta: Mapped[int] = mapped_column(primary_key=True)
    anio_fiscal: Mapped[int] = mapped_column(SmallInteger)
    codigo: Mapped[str] = mapped_column(String(10))
    nombre: Mapped[str] = mapped_column(String(250))
    activa: Mapped[bool] = mapped_column(default=True)


class SaldoMeta(Base):
    __tablename__ = "saldo_meta"

    id_saldo: Mapped[int] = mapped_column(primary_key=True)
    id_meta: Mapped[int] = mapped_column(ForeignKey("meta_presupuestal.id_meta"))
    id_carga: Mapped[int] = mapped_column(ForeignKey("carga_datos.id_carga"))
    pim: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    certificacion: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    compromiso_anual: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class PacItem(Base):
    __tablename__ = "pac_item"

    id_pac_item: Mapped[int] = mapped_column(primary_key=True)
    id_carga: Mapped[int] = mapped_column(ForeignKey("carga_datos.id_carga"))
    numero_referencia: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[str] = mapped_column(String(500))
    tipo_objeto: Mapped[str] = mapped_column(String(12))
    valor_estimado: Mapped[Decimal] = mapped_column(Numeric(14, 2))
