"""Fuente única de la fecha y hora del servidor (Tabla 18 de la Práctica 5).

Se inyecta como dependencia para que las pruebas puedan fijar el momento actual.
"""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import obtener_configuracion

Reloj = Callable[[], datetime]


def ahora() -> datetime:
    return datetime.now(ZoneInfo(obtener_configuracion().zona_horaria))


def obtener_reloj() -> Reloj:
    return ahora


def fecha_local(momento: datetime) -> date:
    return momento.astimezone(ZoneInfo(obtener_configuracion().zona_horaria)).date()
