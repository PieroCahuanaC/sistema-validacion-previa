"""Ambiente de pruebas de integración: base PostgreSQL propia, esquema recreado y datos mock.

Requiere la variable TEST_DATABASE_URL (en CI la define el pipeline con un contenedor
postgres:17.6). Si no existe, las pruebas de integración se omiten.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

URL_PRUEBAS = os.environ.get("TEST_DATABASE_URL")
if URL_PRUEBAS:
    os.environ["DATABASE_URL"] = URL_PRUEBAS  # antes de importar la aplicación

LIMA = ZoneInfo("America/Lima")
AHORA_FIJO = datetime(2026, 10, 25, 10, 0, tzinfo=LIMA)
CORTE_MOCK = datetime(2026, 10, 24, tzinfo=LIMA)


def pytest_collection_modifyitems(config, items):
    if URL_PRUEBAS:
        return
    omitir = pytest.mark.skip(reason="TEST_DATABASE_URL no definida")
    for item in items:
        if "integracion" in str(item.fspath):
            item.add_marker(omitir)


@pytest.fixture(scope="session")
def base_de_datos():
    from alembic import command
    from alembic.config import Config

    from app.core.db import FabricaSesion
    from semillas.cargar import cargar_catalogos, cargar_datos_mock

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(
        os.path.dirname(__file__), "..", "..", "migraciones"))
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    with FabricaSesion() as sesion:
        cargar_catalogos(sesion)
        cargar_datos_mock(sesion, 2026, CORTE_MOCK)
    return FabricaSesion


@pytest.fixture
def sesion(base_de_datos):
    with base_de_datos() as s:
        yield s


@pytest.fixture
def cliente(base_de_datos):
    from fastapi.testclient import TestClient

    from app.core.reloj import obtener_reloj
    from app.main import app

    app.dependency_overrides[obtener_reloj] = lambda: (lambda: AHORA_FIJO)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def cuerpo_base():
    return {
        "meta_codigo": "0012",
        "objeto_contratacion": "BIEN",
        "descripcion": "Asfalto en frío para bacheo de vías vecinales",
        "items": [
            {"descripcion": "Asfalto en frío en bolsa de 25 kg", "unidad_medida": "bolsa",
             "cantidad": "300", "precio_unitario_ref": "42.50", "fuente_precio": "COTIZACION"},
        ],
        "fecha_necesidad": "2026-11-20",
        "pac_item_referencia": "PAC-001",
    }
