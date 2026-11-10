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


TextoOpcional = Annotated[str, StringConstraints(strip_whitespace=True)]


class EspecificacionItem(BaseModel):
    """Especificación técnica de un ítem ya registrado en el paso 1 (no se cambia el ítem)."""

    model_config = ConfigDict(extra="forbid")

    id_item: int
    especificacion: Annotated[TextoOpcional, StringConstraints(max_length=1000)] | None = None


class Paso2Entrada(BaseModel):
    """Paso 2 de la P03; se puede guardar incompleto con «Guardar y continuar después»."""

    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[EspecificacionItem], Field(max_length=50)] = []
    plazo_entrega_dias: Annotated[int, Field(gt=0, le=32767)] | None = None
    lugar_entrega: Annotated[TextoOpcional, StringConstraints(max_length=250)] | None = None


class DocumentosEnvio(BaseModel):
    """Casillas de los documentos que se adjuntan al expediente físico (no se almacenan)."""

    model_config = ConfigDict(extra="forbid")

    documento_requerimiento_firmado: bool
    cuadro_necesidades: bool
    especificaciones_tecnicas_tdr: bool


class EnvioEntrada(Paso2Entrada):
    """«Enviar a la Gerencia de Administración»: guarda el paso 2 y lo envía en un solo acto."""

    documentos: DocumentosEnvio


class ResultadoEnvio(BaseModel):
    requerimiento_id: int
    codigo: str
    fecha_envio: datetime


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
    id_item: int
    descripcion: str
    especificacion: str | None
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
    columna_comparacion: str
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
    # Semáforo vigente (RI-20): el calculado, corregido por la decisión de Presupuesto.
    semaforo_vigente: str
    confirmado_por_presupuesto: bool
    # Paso 2 (cambio 15 de la Práctica 7).
    plazo_entrega_dias: int | None
    lugar_entrega: str | None
    fecha_envio: datetime | None
    puede_completar_paso_2: bool


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


class ReglaVigenteSalida(BaseModel):
    """Parámetros públicos de la regla vigente que la interfaz necesita para validar (P03)."""

    valor_uit: Decimal
    tope_8_uit: Decimal
    antiguedad_maxima_dias: int
