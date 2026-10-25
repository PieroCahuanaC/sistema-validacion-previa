"""Errores de la API en formato Problem Details (RFC 9457), sección 1.7 de la Práctica 5.

Un semáforo rojo o ámbar NO es un error: es un resultado válido de la regla de negocio.
Los errores son solo las situaciones en las que el sistema no puede completar lo pedido.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

TIPO_PROBLEMA = "application/problem+json"


class ErrorNegocio(Exception):
    """Error controlado de la lógica de negocio, con su código HTTP."""

    def __init__(self, estado_http: int, titulo: str, detalle: str) -> None:
        super().__init__(detalle)
        self.estado_http = estado_http
        self.titulo = titulo
        self.detalle = detalle


class NoEncontrado(ErrorNegocio):
    def __init__(self, detalle: str) -> None:
        super().__init__(404, "Recurso no encontrado", detalle)


class DatosNoValidos(ErrorNegocio):
    def __init__(self, detalle: str) -> None:
        super().__init__(422, "Datos de entrada no válidos", detalle)


def _respuesta(estado: int, titulo: str, detalle: str, extra: dict | None = None) -> JSONResponse:
    cuerpo = {"type": "about:blank", "title": titulo, "status": estado, "detail": detalle}
    if extra:
        cuerpo.update(extra)
    return JSONResponse(status_code=estado, content=cuerpo, media_type=TIPO_PROBLEMA)


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorNegocio)
    async def _error_negocio(_: Request, exc: ErrorNegocio) -> JSONResponse:
        return _respuesta(exc.estado_http, exc.titulo, exc.detalle)

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        errores = [
            {"campo": ".".join(str(p) for p in e["loc"][1:]), "mensaje": e["msg"]}
            for e in exc.errors()
        ]
        return _respuesta(
            422, "Datos de entrada no válidos", "Revise los campos indicados.", {"errores": errores}
        )
