"""Conexión a la base de datos y sesión por petición (patrón unidad de trabajo)."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.conexion import argumentos_del_motor
from app.core.config import obtener_configuracion

_config = obtener_configuracion()
motor = create_engine(_config.url_sqlalchemy, **argumentos_del_motor(_config))
FabricaSesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def obtener_sesion() -> Iterator[Session]:
    """Entrega una sesión por petición; la transacción la confirma o revierte el servicio."""
    with FabricaSesion() as sesion:
        yield sesion
