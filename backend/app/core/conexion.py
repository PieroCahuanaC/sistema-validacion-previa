"""Parámetros del pool de conexiones, sin crear el motor (se pueden probar sin base)."""

from app.core.config import Configuracion


def argumentos_del_motor(config: Configuracion) -> dict:
    """Parámetros del pool (defectos DEF-01 y DEF-03 de la Práctica 9).

    El pool es pequeño y fijo porque el pooler de Supabase en modo sesión admite solo 15
    clientes en total, compartidos con la extracción del MEF. Con el pooler en modo
    transacción se desactivan las sentencias preparadas de psycopg, que ese modo no admite.
    """
    argumentos: dict = {
        "pool_pre_ping": True, "pool_size": config.bd_pool_tamano,
        "max_overflow": config.bd_pool_extra, "pool_timeout": 10,
    }
    if config.pooler_en_modo_transaccion:
        argumentos["connect_args"] = {"prepare_threshold": None}
    return argumentos
