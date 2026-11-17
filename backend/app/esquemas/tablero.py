"""DTO del tablero de visibilidad (P06; CU-02, RF-06 a RF-08; Tabla 7 de la Práctica 7)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

Orden = Literal["meta", "codigo", "objeto", "unidad", "monto", "saldo", "fecha_necesidad",
                "tiempo"]


class TarjetasTablero(BaseModel):
    """Conteos de los requerimientos en trámite; los cerrados se cuentan aparte."""

    en_tramite: int
    verde: int
    ambar: int
    rojo: int
    observado: int
    cuello_de_botella: int
    cerrados: int


class FilaTablero(BaseModel):
    requerimiento_id: int
    codigo: str
    descripcion: str
    objeto_contratacion: str
    unidad_sigla: str
    meta_codigo: str
    meta_nombre: str
    monto_estimado: Decimal
    saldo_disponible: Decimal | None
    fecha_necesidad: date
    semaforo_vigente: str
    estado_codigo: str
    estado_actual: str
    horas_en_etapa: float | None
    plazo_horas: int | None
    cuello_de_botella: bool
    cerrado: bool


class MetaFiltro(BaseModel):
    codigo: str
    nombre: str


class TableroSalida(BaseModel):
    tarjetas: TarjetasTablero
    fecha_corte_mef: datetime | None
    unidad: str | None  # vista del Área Usuaria: su unidad, fija
    metas: list[MetaFiltro]
    filas: list[FilaTablero]
    total_filas: int
    pagina: int
    paginas: int
    por_pagina: int
