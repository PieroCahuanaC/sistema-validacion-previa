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
    # Sin valor por defecto: la cadena incluye la contraseña y nunca se escribe en el código
    # (hallazgo de SonarQube "credenciales en el código"). Se define en backend/.env o en Render.
    database_url: str = ""
    cors_origins: str = "http://localhost:4321"
    zona_horaria: str = "America/Lima"
    # Sigla de la unidad orgánica del usuario provisional del incremento 1.
    usuario_provisional_unidad: str = "GDUR"

    @property
    def documentacion_habilitada(self) -> bool:
        """La documentación interactiva de la API solo se expone en desarrollo (CC-01)."""
        return self.ambiente == "desarrollo"

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
