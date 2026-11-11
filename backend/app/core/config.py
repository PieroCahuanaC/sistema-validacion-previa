"""Configuración por ambiente (desarrollo, calidad, producción).

Cada ambiente tiene su propia base de datos; los valores se leen de variables
de entorno y nunca se escriben en el código.
"""

import secrets
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ambiente: Literal["desarrollo", "calidad", "produccion"] = "desarrollo"
    # Sin valor por defecto: la cadena incluye la contraseña y nunca se escribe en el código
    # (hallazgo de SonarQube "credenciales en el código"). Se define en backend/.env o en Render.
    database_url: str = ""
    cors_origins: str = "http://localhost:4321"
    zona_horaria: str = "America/Lima"
    # Clave para firmar los tokens de acceso (JWT). Es un secreto: se define por ambiente
    # (variable CLAVE_JWT en Render) y nunca se escribe en el código.
    clave_jwt: str = ""
    # Clave maestra para cifrar los datos personales de proveedores persona natural
    # (AES-256-GCM) y para el resumen HMAC del RUC: 64 caracteres hexadecimales.
    clave_cifrado: str = ""

    @property
    def documentacion_habilitada(self) -> bool:
        """La documentación interactiva de la API solo se expone en desarrollo (CC-01)."""
        return self.ambiente == "desarrollo"

    @property
    def cookie_segura(self) -> bool:
        """Atributo Secure de las cookies: siempre fuera del ambiente local de desarrollo."""
        return self.ambiente != "desarrollo"

    @property
    def lista_cors(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origins.split(",") if origen.strip()]

    @property
    def url_sqlalchemy(self) -> str:
        """Normaliza la cadena de Supabase/Render (postgresql://) al driver psycopg 3."""
        url = self.database_url
        if not url:
            raise RuntimeError("Defina la variable DATABASE_URL (ver backend/.env.example).")
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()


@lru_cache
def clave_firma() -> str:
    """Clave de los JWT. Falla cerrada si falta fuera del ambiente de desarrollo.

    En desarrollo, si no se define, se genera una al iniciar: las sesiones se pierden al
    reiniciar el servidor, lo que es aceptable con datos mock.
    """
    config = obtener_configuracion()
    if config.clave_jwt:
        return config.clave_jwt
    if config.ambiente != "desarrollo":
        raise RuntimeError("Defina la variable CLAVE_JWT para firmar las sesiones.")
    return secrets.token_hex(32)


@lru_cache
def clave_maestra_cifrado() -> bytes:
    """Clave de cifrado de datos personales. Falla cerrada fuera de desarrollo.

    En desarrollo, si no se define, se genera una al iniciar: los datos cifrados con ella no
    podrán leerse después de reiniciar la API (se muestran como «no disponible»).
    """
    config = obtener_configuracion()
    if config.clave_cifrado:
        try:
            clave = bytes.fromhex(config.clave_cifrado)
        except ValueError as error:
            raise RuntimeError("CLAVE_CIFRADO debe ser hexadecimal.") from error
        if len(clave) != 32:
            raise RuntimeError("CLAVE_CIFRADO debe tener 64 caracteres hexadecimales.")
        return clave
    if config.ambiente != "desarrollo":
        raise RuntimeError("Defina la variable CLAVE_CIFRADO para proteger los datos personales.")
    return secrets.token_bytes(32)
