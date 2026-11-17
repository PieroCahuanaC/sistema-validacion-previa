"""DTO de la configuración del Jefe de Presupuesto: reglas del semáforo (P14) y base
presupuestal con carga CSV de respaldo (P15). Tablas 15 y 16 de la Práctica 7.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Tamaño máximo del archivo CSV que se envía desde la P15 (la base de Uchumayo tiene decenas de
# metas y el PAC algunos cientos de ítems: 2 MB sobra y evita abusar del servidor).
MAX_CARACTERES_CSV = 2_000_000


# --- P14. Reglas del semáforo -------------------------------------------------------------
class ParametrosSemaforo(BaseModel):
    """Contenido de regla_semaforo.parametros con los rangos de la Tabla 15 de la P7."""

    model_config = ConfigDict(extra="forbid")

    umbral_disponibilidad_pct: Annotated[int, Field(ge=100, le=200)]
    columna_comparacion: Literal["COMPROMISO", "CERTIFICACION"]
    tratamiento_no_previsto_pac: Literal["AMBAR", "VERDE"]
    antiguedad_maxima_dias: Annotated[int, Field(ge=1, le=31)]
    valor_uit: Annotated[Decimal, Field(gt=0, le=Decimal("99999.99"), decimal_places=2)]

    @field_validator("valor_uit")
    @classmethod
    def _dos_decimales(cls, valor: Decimal) -> Decimal:
        return valor.quantize(Decimal("0.01"))  # la semilla guarda 5500.0; se muestra 5500.00

    def a_json(self) -> dict:
        datos = self.model_dump()
        datos["valor_uit"] = float(self.valor_uit)  # mismo formato que la regla inicial
        return datos


class CambioParametro(BaseModel):
    parametro: str
    etiqueta: str
    anterior: str
    nuevo: str


class VersionRegla(BaseModel):
    id_regla: int
    vigente_desde: datetime
    vigente_hasta: datetime | None
    parametros: ParametrosSemaforo
    cambios: list[CambioParametro]
    registrado_por: str


class ReglasSalida(BaseModel):
    id_regla: int
    vigente_desde: datetime
    parametros: ParametrosSemaforo
    historial: list[VersionRegla]


# --- P15. Base presupuestal y carga CSV de respaldo ---------------------------------------
class CargaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fuente: Literal["MEF", "SEACE"]
    anio_fiscal: Annotated[int, Field(ge=2024, le=2100)]
    fecha_corte: date
    contenido: Annotated[str, Field(min_length=1, max_length=MAX_CARACTERES_CSV)]


class ValidacionCargaSalida(BaseModel):
    """Vista previa: qué se cargaría, sin escribir nada en la base de datos."""

    valido: bool
    fuente: str
    columnas: list[str]
    total_filas: int
    vista_previa: list[dict[str, str]]
    errores: list[str]
    total_errores: int
    avisos: list[str]


class CargaSalida(BaseModel):
    id_carga: int
    fuente: str
    origen: str
    anio_fiscal: int
    fecha_ejecucion: datetime
    fecha_corte: datetime | None
    resultado: str
    detalle_error: str | None


class EstadoFuente(BaseModel):
    fuente: str
    nombre: str
    ultima_ejecucion: CargaSalida | None
    ultima_exitosa: CargaSalida | None
    dias_desde_corte: int | None
    desactualizado: bool


class BasePresupuestalSalida(BaseModel):
    anio_fiscal: int
    antiguedad_maxima_dias: int
    fuentes: list[EstadoFuente]
    historial: list[CargaSalida]
    columnas: dict[str, list[str]]


class ResultadoCarga(BaseModel):
    carga: CargaSalida
    filas: int
    vigente: bool
