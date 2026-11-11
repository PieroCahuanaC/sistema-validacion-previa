"""Punto de entrada de la API del sistema presupuestal de validación previa."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import autenticacion, inicio, requerimientos, usuarios
from app.core.config import obtener_configuracion
from app.core.errores import TIPO_PROBLEMA, registrar_manejadores

config = obtener_configuracion()

app = FastAPI(
    title="Sistema presupuestal de validación previa",
    version="0.2.0",
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
for modulo in (autenticacion, inicio, requerimientos, usuarios):
    app.include_router(modulo.router, prefix="/api/v1")

METODOS_QUE_MODIFICAN = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@app.middleware("http")
async def verificar_origen(request: Request, call_next):
    """Defensa contra CSRF (Tabla 13 de la P5): las operaciones que modifican datos solo se
    aceptan desde el origen del frontend, además de la cookie SameSite=Strict."""
    origen = request.headers.get("origin")
    if request.method in METODOS_QUE_MODIFICAN and origen and origen not in config.lista_cors:
        return JSONResponse(status_code=403, media_type=TIPO_PROBLEMA, content={
            "type": "about:blank", "title": "Acceso denegado", "status": 403,
            "detail": "Origen no permitido."})
    return await call_next(request)


@app.get("/api/v1/salud", tags=["sistema"])
def salud() -> dict[str, str]:
    """Verificación de disponibilidad usada por Render y por el pipeline."""
    return {"estado": "ok", "ambiente": config.ambiente}
