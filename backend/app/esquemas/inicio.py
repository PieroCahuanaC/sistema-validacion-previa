"""DTO de la pantalla Inicio (P02)."""

from datetime import datetime

from pydantic import BaseModel


class TarjetasSalida(BaseModel):
    verde: int
    ambar: int
    rojo: int
    observado: int
    cuello_de_botella: int


class PendienteSalida(BaseModel):
    requerimiento_id: int
    codigo: str
    descripcion: str
    situacion: str
    motivo: str
    desde: datetime
    accion: str
    destino: str


class InicioSalida(BaseModel):
    fecha_corte_mef: datetime | None
    fecha_corte_seace: datetime | None
    tarjetas: TarjetasSalida | None
    pendientes: list[PendienteSalida]
    pendientes_disponibles: bool
