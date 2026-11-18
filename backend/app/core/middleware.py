"""Middleware ASGI de la API: control de concurrencia y cabeceras de seguridad.

Control de concurrencia (defecto DEF-01 de la Práctica 9). Los endpoints son síncronos: cada
petición pasa varias veces por el grupo de hilos de AnyIO (40 hilos) y, mientras tanto,
retiene una conexión del pool de SQLAlchemy (por defecto 10). En la prueba de carga, con 50
usuarios, los 40 hilos quedaron esperando una conexión y las conexiones quedaron retenidas
por peticiones que esperaban un hilo: el servidor dejó de responder y no se recuperó al
terminar la carga. Este middleware admite a la vez solo tantas peticiones como conexiones
tiene el pool; las demás esperan su turno sin ocupar hilos y, si el turno no llega en
ESPERA_TURNO_SEGUNDOS, reciben 503 con Retry-After. La API se degrada, pero no se bloquea.

Cabeceras de seguridad (defecto DEF-05). La API también responde directamente en su dominio
de Render, sin pasar por Vercel, así que fija sus propias cabeceras.
"""

import asyncio
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

RUTAS_SIN_LIMITE = frozenset({"/api/v1/salud"})  # verificación de Render: nunca se encola

CABECERAS_SEGURIDAD = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"same-origin"),
    # La API solo devuelve JSON: no carga ni ejecuta nada.
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cache-control", b"no-store"),
]


class LimiteDeConcurrencia:
    def __init__(self, app: ASGIApp, maximo: int, espera_segundos: float) -> None:
        self.app = app
        self.maximo = maximo
        self.espera = espera_segundos
        self._turnos: asyncio.Semaphore | None = None

    @property
    def turnos(self) -> asyncio.Semaphore:
        # Se crea en el primer uso, dentro del bucle de eventos del servidor.
        if self._turnos is None:
            self._turnos = asyncio.Semaphore(self.maximo)
        return self._turnos

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in RUTAS_SIN_LIMITE:
            await self.app(scope, receive, send)
            return
        try:
            await asyncio.wait_for(self.turnos.acquire(), timeout=self.espera)
        except TimeoutError:
            await _servicio_ocupado(send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            self.turnos.release()


async def _servicio_ocupado(send: Send) -> None:
    cuerpo = json.dumps({
        "type": "about:blank", "title": "Servicio ocupado", "status": 503,
        "detail": "El sistema está atendiendo muchas solicitudes. Intente de nuevo en unos "
                  "segundos.",
    }, ensure_ascii=False).encode()
    await send({"type": "http.response.start", "status": 503, "headers": [
        (b"content-type", b"application/problem+json"), (b"retry-after", b"5"),
        (b"content-length", str(len(cuerpo)).encode()), *CABECERAS_SEGURIDAD]})
    await send({"type": "http.response.body", "body": cuerpo})


class CabecerasDeSeguridad:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Solo la API; /docs (Swagger, solo en desarrollo) carga recursos externos.
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                presentes = {k.lower() for k, _ in mensaje.get("headers", [])}
                mensaje["headers"] = [*mensaje.get("headers", []),
                                      *((k, v) for k, v in CABECERAS_SEGURIDAD
                                        if k not in presentes)]
            await send(mensaje)

        await self.app(scope, receive, enviar)
