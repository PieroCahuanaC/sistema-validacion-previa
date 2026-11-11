"""Contraseñas: hash Argon2id con sal por usuario y reglas mínimas (Tabla 13 de la P5).

La contraseña en texto plano nunca se almacena ni se registra en la bitácora.
"""

import re
import secrets
import string

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_hasher = PasswordHash((Argon2Hasher(),))

LONGITUD_MINIMA = 12
LONGITUD_MAXIMA = 128
# Muestra de contraseñas y bases más usadas; se compara sin mayúsculas ni números finales.
COMUNES = frozenset({
    "contrasena", "contraseña", "password", "123456789012", "qwertyuiopas", "administrador",
    "municipalidad", "uchumayo", "arequipa", "presupuesto", "bienvenido", "peru", "admin",
    "usuario", "iloveyou", "qwerty", "abc123", "letmein", "welcome", "logistica",
})
REGLAS = (
    f"Al menos {LONGITUD_MINIMA} caracteres",
    "No es una contraseña común ni el nombre de la municipalidad",
    "Distinta de su nombre de usuario",
)


def hashear(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar(contrasena: str, hash_guardado: str) -> bool:
    try:
        return _hasher.verify(contrasena, hash_guardado)
    except Exception:  # hash con formato inválido: se trata como contraseña incorrecta
        return False


def incumplimientos(contrasena: str, nombre_usuario: str) -> list[str]:
    """Reglas que la contraseña no cumple; lista vacía si es aceptable."""
    faltas = []
    if len(contrasena) < LONGITUD_MINIMA or len(contrasena) > LONGITUD_MAXIMA:
        faltas.append(REGLAS[0])
    base = re.sub(r"[\d\W_]+$", "", contrasena.lower())
    if base in COMUNES or len(set(contrasena)) <= 2:
        faltas.append(REGLAS[1])
    if nombre_usuario and nombre_usuario.lower() in contrasena.lower():
        faltas.append(REGLAS[2])
    return faltas


def generar_temporal() -> str:
    """Contraseña temporal aleatoria de 16 caracteres, sin caracteres ambiguos."""
    alfabeto = "".join(c for c in string.ascii_letters + string.digits if c not in "0OolI1")
    return "".join(secrets.choice(alfabeto) for _ in range(16))
