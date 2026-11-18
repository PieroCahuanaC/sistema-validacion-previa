"""Pruebas de integración de las correcciones de la Práctica 9 en la aplicación completa.
CP-I68 (cabeceras de seguridad, DEF-05) y CP-I69 (turno de atención, DEF-01).
"""

from concurrent.futures import ThreadPoolExecutor

from app.core.middleware import LimiteDeConcurrencia
from app.main import app


def test_cpi68_cabeceras_de_seguridad_en_respuestas_de_la_api(como):
    anonimo = como(None)
    for respuesta in (anonimo.get("/api/v1/salud"), anonimo.get("/api/v1/metas")):
        assert respuesta.headers["x-content-type-options"] == "nosniff"
        assert respuesta.headers["x-frame-options"] == "DENY"
        assert respuesta.headers["content-security-policy"].startswith("default-src 'none'")
        assert respuesta.headers["cache-control"] == "no-store"
    assert anonimo.get("/api/v1/metas").status_code == 401  # también en los errores


def test_cpi69_la_api_completa_atiende_por_turnos(como):
    limite = next(m for m in app.user_middleware if m.cls is LimiteDeConcurrencia)
    # El máximo de turnos es igual a las conexiones del pool (5 + 5 por defecto).
    assert limite.kwargs["maximo"] == 10
    cliente = como("AU")
    # Treinta consultas a la vez, el triple de los turnos: las que esperan se atienden al
    # liberarse un turno y todas terminan bien. La prueba de carga es la evidencia de fondo.
    with ThreadPoolExecutor(max_workers=30) as hilos:
        codigos = list(hilos.map(lambda _: cliente.get("/api/v1/metas").status_code, range(30)))
    assert codigos == [200] * 30
    assert cliente.get("/api/v1/salud").status_code == 200
