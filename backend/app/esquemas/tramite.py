"""DTO del trámite del expediente: cambios de etapa, ajustes, decisiones, listas e historial.

Corresponden a los endpoints PATCH /requerimientos/{id}/etapa, POST /requerimientos/{id}/
ajustes, GET /alertas, POST /alertas/{id}/decision y GET /requerimientos/{id}/historial del
contrato de la API (Práctica 5), y a las pantallas P05, P07, P08, P11 y P17 (Práctica 7).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.esquemas.requerimiento import Texto

Observacion = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


# --- Cambio de etapa (máquina de estados, Figura 5 de la Práctica 5) -----------------------
class CambioEtapaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destino: Literal["REGISTRADO", "APROBADO", "DOCUMENTACION_VALIDADA", "CUADRO_REGISTRADO",
                     "CERTIFICADO", "ORDEN_EMITIDA", "OBSERVADO", "ANULADO"]
    observacion: Observacion | None = None


class CambioEtapaSalida(BaseModel):
    requerimiento_id: int
    codigo: str
    estado_anterior: str
    estado_actual: str
    fecha_hora: datetime


# --- P05. Aplicar ajuste sugerido (CU-05, RF-04) ------------------------------------------
class ItemAjuste(BaseModel):
    """Ítem del requerimiento reformulado.

    Con id_item_original es un ítem que se conserva: solo puede bajar su cantidad y su precio
    queda bloqueado (RI-26). Sin id_item_original es un ítem nuevo que reemplaza a otro, y
    exige descripción, unidad, precio y fuente.
    """

    model_config = ConfigDict(extra="forbid")

    id_item_original: int | None = None
    cantidad: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    descripcion: Annotated[Texto, StringConstraints(max_length=250)] | None = None
    unidad_medida: Annotated[Texto, StringConstraints(max_length=30)] | None = None
    precio_unitario_ref: Annotated[Decimal, Field(gt=0, max_digits=14,
                                                  decimal_places=2)] | None = None
    fuente_precio: Literal["COTIZACION", "COMPRA_ANTERIOR"] | None = None


class AjusteEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opcion: Literal["REFORMULAR", "REPROGRAMAR", "NINGUNA"]
    items: Annotated[list[ItemAjuste], Field(max_length=50)] | None = None
    fecha_necesidad_nueva: date | None = None


class ResultadoAjuste(BaseModel):
    requerimiento_id: int
    codigo: str
    opcion: str
    monto_estimado: Decimal
    fecha_necesidad: date
    revalidado: bool
    estado_semaforo: str | None
    motivo: str | None
    semaforo_vigente: str


# --- P11. Panel de alertas (CU-06, RF-09) -------------------------------------------------
class DecisionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resultado: Literal["CONFIRMADA", "DENEGADA"]
    sustento: Observacion | None = None


class DecisionSalida(BaseModel):
    requerimiento_id: int
    codigo: str
    resultado: str
    sustento: str | None
    fecha_hora: datetime
    semaforo_vigente: str


class AlertaSalida(BaseModel):
    requerimiento_id: int
    codigo: str
    descripcion: str
    unidad_sigla: str
    meta_codigo: str
    monto_evaluado: Decimal
    motivo: str
    fecha_corte: datetime | None
    fecha_validacion: datetime
    dias_en_alerta: int
    estado_actual: str
    opcion_ajuste: str | None


class AlertasSalida(BaseModel):
    ambar: list[AlertaSalida]
    rojo: list[AlertaSalida]


# --- P08. Bandeja de aprobación (CU-11, RF-13) --------------------------------------------
class BandejaFila(BaseModel):
    requerimiento_id: int
    codigo: str
    descripcion: str
    unidad_sigla: str
    unidad_nombre: str
    meta_codigo: str
    meta_nombre: str
    objeto_contratacion: str
    monto_estimado: Decimal
    fecha_necesidad: date
    semaforo: str
    confirmado_por_presupuesto: bool
    motivo: str
    fecha_validacion: datetime
    fecha_envio: datetime
    horas_en_bandeja: float
    plazo_horas: int | None
    excedido: bool


# --- P17. Mis requerimientos (CU-04) -------------------------------------------------------
class MiRequerimientoFila(BaseModel):
    requerimiento_id: int
    codigo: str
    descripcion: str
    meta_codigo: str
    monto_estimado: Decimal
    semaforo: str
    semaforo_vigente: str
    estado_codigo: str
    estado_actual: str
    fecha_necesidad: date
    fecha_registro: datetime
    accion: str | None
    destino: str


# --- P07. Historial de trazabilidad (CU-02, CU-10; RF-05 a RF-07) -------------------------
class RegistroHistorial(BaseModel):
    estado_codigo: str
    estado: str
    fecha_hora: datetime
    rol: str
    observacion: str | None
    horas_en_etapa: float | None
    plazo_horas: int | None
    excedio_plazo: bool
    en_curso: bool


class EtapaFutura(BaseModel):
    estado_codigo: str
    estado: str


class HistorialSalida(BaseModel):
    requerimiento_id: int
    codigo: str
    descripcion: str
    meta_codigo: str
    monto_estimado: Decimal
    semaforo: str
    semaforo_vigente: str
    estado_actual: str
    cerrado: bool
    responsable_actual: str
    accion_pendiente: str
    registros: list[RegistroHistorial]
    etapas_futuras: list[EtapaFutura]
    horas_hasta_certificacion: float | None
    horas_totales: float | None
