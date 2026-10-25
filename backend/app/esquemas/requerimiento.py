"""DTO del registro y la consulta del requerimiento (Figura 6 de la Práctica 5).

Los nombres de los campos coinciden con el contrato de la API y con el modelo de datos.
Los datos mal formados se rechazan aquí, antes de llegar a la lógica de negocio.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ItemEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descripcion: Annotated[Texto, StringConstraints(max_length=250)]
    unidad_medida: Annotated[Texto, StringConstraints(max_length=30)]
    cantidad: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    precio_unitario_ref: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    fuente_precio: Literal["COTIZACION", "COMPRA_ANTERIOR"]


class RequerimientoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta_codigo: Annotated[Texto, StringConstraints(max_length=10)]
    objeto_contratacion: Literal["BIEN", "SERVICIO"]
    descripcion: Annotated[Texto, StringConstraints(max_length=500)]
    items: Annotated[list[ItemEntrada], Field(min_length=1, max_length=50)]
    fecha_necesidad: date
    # Obligatorio pero admite nulo: el Área Usuaria declara expresamente que no está previsto.
    pac_item_referencia: Annotated[str, StringConstraints(max_length=20)] | None


class ResultadoRegistro(BaseModel):
    requerimiento_id: int
    codigo: str
    monto_estimado: Decimal
    estado_semaforo: str
    motivo: str
    saldo_disponible_meta: Decimal | None
    previsto_en_pac: bool
    fecha_corte_datos: datetime | None
    opciones_ajuste: list[str]


class ItemSalida(BaseModel):
    descripcion: str
    unidad_medida: str
    cantidad: Decimal
    precio_unitario_ref: Decimal
    fuente_precio: str
    subtotal: Decimal


class EtapaSalida(BaseModel):
    codigo: str
    nombre: str
    rol_a_cargo: str
    cumplida: bool
    actual: bool
    fecha_hora: datetime | None = None
    rol_registro: str | None = None
    observacion: str | None = None


class BaseCalculo(BaseModel):
    pim: Decimal | None
    certificacion: Decimal | None
    compromiso_anual: Decimal | None
    saldo_disponible: Decimal | None
    monto_evaluado: Decimal
    fecha_corte: datetime | None
    previsto_en_pac: bool
    pac_item_referencia: str | None


class SemaforoSalida(BaseModel):
    estado: str
    motivo: str
    fecha_hora: datetime
    base_calculo: BaseCalculo
    opciones_ajuste: list[str]


class RequerimientoDetalle(BaseModel):
    requerimiento_id: int
    codigo: str
    unidad_organica: str
    meta_codigo: str
    meta_nombre: str
    objeto_contratacion: str
    descripcion: str
    monto_estimado: Decimal
    fecha_necesidad: date
    fecha_registro: datetime
    estado_actual: str
    responsable_actual: str
    accion_pendiente: str
    items: list[ItemSalida]
    etapas: list[EtapaSalida]
    semaforo: SemaforoSalida


class MetaSalida(BaseModel):
    codigo: str
    nombre: str
    saldo_disponible: Decimal | None
    fecha_corte: datetime | None


class PacItemSalida(BaseModel):
    numero_referencia: str
    descripcion: str
    tipo_objeto: str
    valor_estimado: Decimal
