"""Protección de los datos personales de proveedores persona natural (Ley N.° 29733; Tabla 10
y sección 1.9 de la Práctica 6).

- El RUC y la razón social (nombre) de una persona natural se cifran con AES-256-GCM: cada
  valor lleva su propio nonce aleatorio y una etiqueta de autenticación, de modo que un
  cambio en la base de datos se detecta al descifrar.
- ruc_hash es un HMAC-SHA256 del RUC con una clave secreta: permite buscar y evitar
  duplicados sin descifrar. Un SHA-256 sin clave no basta, porque los RUC tienen solo 11
  dígitos y se podrían adivinar probándolos todos.
Las dos claves se derivan de CLAVE_CIFRADO con HKDF, para no reutilizar la misma clave en dos
algoritmos distintos.
"""

import base64
import hashlib
import hmac
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import clave_maestra_cifrado

PREFIJO = "v1:"
CONTEXTO = b"svp-proveedor"
NO_DISPONIBLE = "[dato cifrado no disponible]"


def _derivar(proposito: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=b"svp/" + proposito).derive(clave_maestra_cifrado())


@lru_cache
def _clave_aes() -> bytes:
    return _derivar(b"aes-gcm")


@lru_cache
def _clave_hmac() -> bytes:
    return _derivar(b"hmac-ruc")


def cifrar(texto: str) -> str:
    nonce = os.urandom(12)
    datos = AESGCM(_clave_aes()).encrypt(nonce, texto.encode("utf-8"), CONTEXTO)
    return PREFIJO + base64.b64encode(nonce + datos).decode("ascii")


def descifrar(valor: str) -> str:
    """Descifra un valor; si no es un valor cifrado lo devuelve tal cual (persona jurídica)."""
    if not valor.startswith(PREFIJO):
        return valor
    try:
        crudo = base64.b64decode(valor[len(PREFIJO):])
        return AESGCM(_clave_aes()).decrypt(crudo[:12], crudo[12:], CONTEXTO).decode("utf-8")
    except (InvalidTag, ValueError):
        return NO_DISPONIBLE


def resumen_ruc(ruc: str) -> str:
    return hmac.new(_clave_hmac(), ruc.encode("ascii"), hashlib.sha256).hexdigest()


def ruc_valido(ruc: str) -> bool:
    """RUC de 11 dígitos con dígito verificador correcto (módulo 11 de la SUNAT)."""
    if len(ruc) != 11 or not ruc.isdigit():
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    resto = 11 - sum(int(d) * p for d, p in zip(ruc[:10], pesos, strict=True)) % 11
    verificador = {10: 0, 11: 1}.get(resto, resto)
    return verificador == int(ruc[10])


def ocultar_ruc(ruc: str) -> str:
    """RUC parcialmente oculto para mostrarlo sin exponerlo completo: 10•••••••92."""
    return ruc[:2] + "•" * 7 + ruc[-2:] if len(ruc) == 11 else ruc
