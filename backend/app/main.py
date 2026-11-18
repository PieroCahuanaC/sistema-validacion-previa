"""Punto de entrada de la API del sistema presupuestal de validación previa."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    autenticacion,
    configuracion,
    inicio,
    logistica,
    requerimientos,
    tablero,
    tramite,
    usuarios,
)
from app.core.config import obtener_configuracion
from app.core.errores import TIPO_PROBLEMA, registrar_manejadores
from app.core.middleware import CabecerasDeSeguridad, LimiteDeConcurrencia

config = obtener_configuracion()

app = FastAPI(
    title="Sistema presupuestal de validación previa",
    version="0.5.0",
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
for modulo in (autenticacion, configuracion, inicio, logistica, requerimientos, tablero, tramite,
               usuarios):
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


# Se agregan al final para que envuelvan a todo lo anterior (el último agregado es el más
# externo): primero las cabeceras de seguridad y luego el turno de atención (DEF-01, DEF-05).
app.add_middleware(LimiteDeConcurrencia, maximo=config.max_peticiones_simultaneas,
                   espera_segundos=config.espera_turno_segundos)
app.add_middleware(CabecerasDeSeguridad)


@app.get("/api/v1/salud", tags=["sistema"])
def salud() -> dict[str, str]:
    """Verificación de disponibilidad usada por Render y por el pipeline."""
    return {"estado": "ok", "ambiente": config.ambiente}
