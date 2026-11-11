"""DTO de Logística y certificación: validación documental (P09), cuadro comparativo (P10),
certificación (P12) y orden (P13); CU-07, CU-08, CU-13 y CU-14."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.esquemas.tramite import Observacion

Ruc = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{11}$")]
RazonSocial = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2,
                                               max_length=300)]
Monto = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


# --- P09. Validación documental -----------------------------------------------------------
class DocumentoRevision(BaseModel):
    id_tipo_documento: int
    nombre: str
    obligatorio: bool
    ultimo_resultado: str | None
    ultima_observacion: str | None
    ultima_fecha: datetime | None


class RevisionSalida(BaseModel):
    requerimiento_id: int
    puede_revisar: bool
    documentos: list[DocumentoRevision]


class ResultadoDocumento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_tipo_documento: int
    resultado: Literal["CONFORME", "OBSERVADO"]
    observacion: Observacion | None = None


class RevisionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentos: Annotated[list[ResultadoDocumento], Field(min_length=1, max_length=20)]


class RevisionResultado(BaseModel):
    requerimiento_id: int
    codigo: str
    resultado: Literal["VALIDADA", "DEVUELTA"]
    estado_actual: str


# --- Proveedores ---------------------------------------------------------------------------
class ProveedorNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_persona: Literal["NATURAL", "JURIDICA"]
    ruc: Ruc
    razon_social: RazonSocial


class ProveedorSalida(BaseModel):
    id_proveedor: int
    tipo_persona: str
    ruc: str
    razon_social: str


class BusquedaProveedor(BaseModel):
    encontrado: bool
    proveedor: ProveedorSalida | None


# --- P10. Cuadro comparativo ---------------------------------------------------------------
class CotizacionEntrada(BaseModel):
    """Cotización con un proveedor ya registrado (id_proveedor) o uno nuevo (proveedor)."""

    model_config = ConfigDict(extra="forbid")

    id_proveedor: int | None = None
    proveedor: ProveedorNuevo | None = None
    monto: Monto
    fecha_cotizacion: date


class CuadroEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cotizaciones: Annotated[list[CotizacionEntrada], Field(min_length=1, max_length=20)]
    precio_referencia: Monto
    observacion: Observacion | None = None


class CotizacionSalida(BaseModel):
    id_cotizacion: int
    monto: Decimal
    fecha_cotizacion: date
    # Solo para Logística: el Jefe de Presupuesto no ve los datos del proveedor (P12).
    proveedor: ProveedorSalida | None


class CuadroSalida(BaseModel):
    requerimiento_id: int
    existe: bool
    modo: Literal["REGISTRO", "CORRECCION", "CONSULTA"]
    monto_validado: Decimal
    precio_referencia: Decimal | None
    observacion: str | None
    fecha_registro: datetime | None
    menor_cotizacion: Decimal | None
    promedio: Decimal | None
    cotizaciones: list[CotizacionSalida]
    devolucion_presupuesto: str | None


class CuadroResultado(BaseModel):
    requerimiento_id: int
    codigo: str
    modo: Literal["REGISTRO", "CORRECCION"]
    revalidado: bool
    estado_semaforo: str | None
    semaforo_vigente: str
    estado_actual: str
    destino: Literal["PRESUPUESTO", "AREA_USUARIA"]


# --- Listas de Logística y Presupuesto (P09, P10, P12, P13) --------------------------------
class ExpedienteFila(BaseModel):
    requerimiento_id: int
    codigo: str
    descripcion: str
    unidad_sigla: str
    meta_codigo: str
    objeto_contratacion: str
    monto_estimado: Decimal
    precio_referencia: Decimal | None
    semaforo_vigente: str
    confirmado_por_presupuesto: bool
    estado_codigo: str
    estado_actual: str
    desde: datetime
    horas_en_etapa: float
    plazo_horas: int | None
    excedido: bool
    devuelto: bool
    nota: str | None
