"""Punto de entrada de la API del sistema presupuestal de validación previa."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import requerimientos
from app.core.config import obtener_configuracion
from app.core.errores import registrar_manejadores

config = obtener_configuracion()

app = FastAPI(
    title="Sistema presupuestal de validación previa",
    version="0.1.0",
    docs_url="/docs" if config.documentacion_habilitada else None,
    redoc_url=None,
    openapi_url="/openapi.json" if config.documentacion_habilitada else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.lista_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)
registrar_manejadores(app)
app.include_router(requerimientos.router, prefix="/api/v1")


@app.get("/api/v1/salud", tags=["sistema"])
def salud() -> dict[str, str]:
    """Verificación de disponibilidad usada por Render y por el pipeline."""
    return {"estado": "ok", "ambiente": config.ambiente}
