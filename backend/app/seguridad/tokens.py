"""Tokens de sesión (Tabla 13 de la Práctica 5).

- Acceso: JWT firmado (HS256) de 15 minutos con el usuario, su rol y su sesión.
- Renovación: valor aleatorio de 8 horas como máximo que se rota en cada uso; en la base de
  datos solo se guarda su resumen SHA-256, de modo que puede revocarse.
El vencimiento se compara con el reloj inyectado del servidor, no con el del sistema
operativo, para que las pruebas puedan fijar el momento actual.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

import jwt

from app.core.config import clave_firma

DURACION_ACCESO = timedelta(minutes=15)
DURACION_RENOVACION = timedelta(hours=8)
COOKIE_ACCESO = "svp_acceso"
COOKIE_RENOVACION = "svp_renovacion"
_ALGORITMO = "HS256"


def emitir_acceso(id_usuario: int, codigo_rol: str, id_sesion: int, ahora: datetime) -> str:
    carga = {
        "sub": str(id_usuario), "rol": codigo_rol, "sid": id_sesion,
        "iat": int(ahora.timestamp()), "exp": int((ahora + DURACION_ACCESO).timestamp()),
    }
    return jwt.encode(carga, clave_firma(), algorithm=_ALGORITMO)


def leer_acceso(token: str, ahora: datetime) -> dict | None:
    """Carga del token si la firma es válida y no venció; None en cualquier otro caso."""
    try:
        carga = jwt.decode(token, clave_firma(), algorithms=[_ALGORITMO],
                           options={"verify_exp": False, "require": ["sub", "sid", "exp"]})
    except jwt.PyJWTError:
        return None
    if int(carga["exp"]) <= int(ahora.timestamp()):
        return None
    return carga


def nuevo_token_renovacion() -> tuple[str, str]:
    """Token para la cookie y su resumen para la base de datos."""
    token = secrets.token_urlsafe(32)
    return token, resumen(token)


def resumen(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
