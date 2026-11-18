"""Pruebas unitarias de las correcciones de la Práctica 9: turno de atención (DEF-01),
parámetros del pool y modo transacción del pooler (DEF-03) y cabeceras de seguridad de la
API (DEF-05). CP-U52 a CP-U54.
"""

import asyncio

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.conexion import argumentos_del_motor
from app.core.config import Configuracion
from app.core.middleware import CabecerasDeSeguridad, LimiteDeConcurrencia


def _app_lenta(espera: float) -> Starlette:
    async def lenta(_):
        await asyncio.sleep(espera)
        return JSONResponse({"ok": True})

    async def salud(_):
        return JSONResponse({"estado": "ok"})

    return Starlette(routes=[Route("/api/v1/lenta", lenta), Route("/api/v1/salud", salud)])


def _ejecutar(app, rutas: list[str]) -> list[httpx.Response]:
    async def todas():
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
            return await asyncio.gather(*(cliente.get(r) for r in rutas))
    return asyncio.run(todas())


def test_cpu52_turno_de_atencion_rechaza_con_503_sin_bloquear_el_servidor():
    # Dos turnos, cuatro peticiones lentas a la vez y 0,1 s de espera máxima por turno.
    app = LimiteDeConcurrencia(_app_lenta(0.5), maximo=2, espera_segundos=0.1)
    respuestas = _ejecutar(app, ["/api/v1/lenta"] * 4 + ["/api/v1/salud"])
    codigos = sorted(r.status_code for r in respuestas[:4])
    assert codigos == [200, 200, 503, 503]
    ocupado = next(r for r in respuestas if r.status_code == 503)
    assert ocupado.headers["retry-after"] == "5"
    assert ocupado.headers["content-type"] == "application/problem+json"
    assert ocupado.json()["title"] == "Servicio ocupado"
    assert respuestas[4].status_code == 200  # /salud nunca espera turno
    # Liberados los turnos, el servidor vuelve a atender: no queda bloqueado.
    assert [r.status_code for r in _ejecutar(app, ["/api/v1/lenta"] * 2)] == [200, 200]


@pytest.mark.parametrize(("url", "forzado", "transaccion"), [
    ("postgresql://u:p@aws-0-us-east-1.pooler.supabase.com:6543/postgres", None, True),
    ("postgresql://u:p@aws-0-us-east-1.pooler.supabase.com:5432/postgres", None, False),
    ("postgresql+psycopg://svp:svp@localhost/svp_dev", None, False),  # puerto por defecto
    ("postgresql://u:p@localhost:5432/x", True, True),  # forzado por BD_MODO_TRANSACCION
    ("postgresql://u:p@host:6543/x", False, False),
])
def test_cpu53_pool_y_modo_transaccion_del_pooler(url, forzado, transaccion):
    config = Configuracion(database_url=url, bd_modo_transaccion=forzado, bd_pool_tamano=4,
                           bd_pool_extra=6)
    argumentos = argumentos_del_motor(config)
    assert config.pooler_en_modo_transaccion is transaccion
    assert (argumentos.get("connect_args") == {"prepare_threshold": None}) is transaccion
    assert (argumentos["pool_size"], argumentos["max_overflow"]) == (4, 6)
    assert config.max_peticiones_simultaneas == 10  # turnos = conexiones del pool
    assert Configuracion(database_url="").pooler_en_modo_transaccion is False


def test_cpu54_cabeceras_de_seguridad_solo_en_la_api():
    async def api(_):
        return JSONResponse({"ok": True}, headers={"Cache-Control": "max-age=60"})

    app = CabecerasDeSeguridad(Starlette(routes=[Route("/api/v1/x", api), Route("/docs", api)]))
    en_api, en_docs = _ejecutar(app, ["/api/v1/x", "/docs"])
    assert en_api.headers["x-content-type-options"] == "nosniff"
    assert en_api.headers["content-security-policy"].startswith("default-src 'none'")
    assert en_api.headers["x-frame-options"] == "DENY"
    assert en_api.headers["cache-control"] == "max-age=60"  # no reemplaza las del endpoint
    assert "content-security-policy" not in en_docs.headers  # Swagger carga recursos externos
