"""Requerimiento, sus ítems, su validación y su historial (Tablas 8 y 9 de la Práctica 6)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modelos.base import Base


class Requerimiento(Base):
    __tablename__ = "requerimiento"

    id_requerimiento: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(15))
    id_unidad: Mapped[int] = mapped_column(ForeignKey("unidad_organica.id_unidad"))
    id_meta: Mapped[int] = mapped_column(ForeignKey("meta_presupuestal.id_meta"))
    id_pac_item: Mapped[int | None] = mapped_column(ForeignKey("pac_item.id_pac_item"))
    id_estado_actual: Mapped[int] = mapped_column(ForeignKey("estado.id_estado"))
    objeto_contratacion: Mapped[str] = mapped_column(String(10))
    descripcion: Mapped[str] = mapped_column(String(500))
    monto_estimado: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha_necesidad: Mapped[date]
    fecha_registro: Mapped[datetime]

    items: Mapped[list["RequerimientoItem"]] = relationship(
        order_by="RequerimientoItem.id_item", lazy="selectin"
    )


class RequerimientoItem(Base):
    __tablename__ = "requerimiento_item"

    id_item: Mapped[int] = mapped_column(primary_key=True)
    id_requerimiento: Mapped[int] = mapped_column(ForeignKey("requerimiento.id_requerimiento"))
    descripcion: Mapped[str] = mapped_column(String(250))
    unidad_medida: Mapped[str] = mapped_column(String(30))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    precio_unitario_ref: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fuente_precio: Mapped[str] = mapped_column(String(20))


class ValidacionPresupuestal(Base):
    __tablename__ = "validacion_presupuestal"

    id_validacion: Mapped[int] = mapped_column(primary_key=True)
    id_requerimiento: Mapped[int] = mapped_column(ForeignKey("requerimiento.id_requerimiento"))
    id_saldo: Mapped[int | None] = mapped_column(ForeignKey("saldo_meta.id_saldo"))
    id_regla: Mapped[int] = mapped_column(ForeignKey("regla_semaforo.id_regla"))
    fecha_hora: Mapped[datetime]
    monto_evaluado: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    estado_semaforo: Mapped[str] = mapped_column(String(5))
    motivo: Mapped[str] = mapped_column(String(30))


class HistorialEtapa(Base):
    __tablename__ = "historial_etapa"

    id_historial: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_requerimiento: Mapped[int] = mapped_column(ForeignKey("requerimiento.id_requerimiento"))
    id_estado: Mapped[int] = mapped_column(ForeignKey("estado.id_estado"))
    id_rol: Mapped[int] = mapped_column(ForeignKey("rol.id_rol"))
    fecha_hora: Mapped[datetime]
    observacion: Mapped[str | None] = mapped_column(String(500))
