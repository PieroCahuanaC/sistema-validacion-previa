"""Configuración por ambiente (desarrollo, calidad, producción).

Cada ambiente tiene su propia base de datos; los valores se leen de variables
de entorno y nunca se escriben en el código.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ambiente: Literal["desarrollo", "calidad", "produccion"] = "desarrollo"
    database_url: str = "postgresql+psycopg://svp:svp_dev_local@localhost:5432/svp_dev"
    cors_origins: str = "http://localhost:4321"

    @property
    def documentacion_habilitada(self) -> bool:
        """La documentación interactiva de la API solo se expone en desarrollo (CC-01)."""
        return self.ambiente == "desarrollo"

    @property
    def lista_cors(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origins.split(",") if origen.strip()]


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
