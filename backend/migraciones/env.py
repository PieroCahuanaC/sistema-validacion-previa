"""Entorno de Alembic: aplica las migraciones con la base del ambiente configurado."""

from alembic import context
from sqlalchemy import create_engine

from app.core.config import obtener_configuracion


def ejecutar_migraciones() -> None:
    motor = create_engine(obtener_configuracion().url_sqlalchemy)
    with motor.connect() as conexion:
        context.configure(connection=conexion, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()


ejecutar_migraciones()
