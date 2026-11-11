"""Ambiente de pruebas de integración: base PostgreSQL propia, esquema recreado y datos mock.

Requiere la variable TEST_DATABASE_URL (en CI la define el pipeline con un contenedor
postgres:17.6). Si no existe, las pruebas de integración se omiten.
"""

import os
import secrets
from datetime import datetime, timedelta
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


# Un usuario de prueba por rol. Las contraseñas se generan al ejecutar las pruebas: no hay
# ninguna contraseña escrita en el repositorio.
USUARIOS_DE_PRUEBA = {
    "AU": ("prueba.au", "GDUR"), "AU2": ("prueba.au2", "GSP"), "GA": ("prueba.ga", "GA"),
    "JL": ("prueba.jl", "SGASG"), "JP": ("prueba.jp", "OPP"), "ADM": ("prueba.admin", None),
}


@pytest.fixture(scope="session")
def credenciales(base_de_datos):
    from sqlalchemy import select

    from app.modelos.catalogos import Rol, UnidadOrganica
    from app.modelos.seguridad import Usuario
    from app.seguridad import contrasenas

    resultado = {}
    with base_de_datos() as sesion:
        roles = {r.codigo: r.id_rol for r in sesion.scalars(select(Rol))}
        unidades = {u.sigla: u.id_unidad for u in sesion.scalars(select(UnidadOrganica))}
        for clave, (nombre, sigla) in USUARIOS_DE_PRUEBA.items():
            contrasena = secrets.token_urlsafe(18)
            sesion.add(Usuario(
                nombre_usuario=nombre, nombres_apellidos=f"Usuario de prueba {clave}",
                id_rol=roles[clave[:2] if clave != "ADM" else "ADM"],
                id_unidad=unidades.get(sigla), hash_contrasena=contrasenas.hashear(contrasena),
                contrasena_temporal=False, intentos_fallidos=0, estado="ACTIVO"))
            resultado[clave] = (nombre, contrasena)
        sesion.commit()
    return resultado


@pytest.fixture
def sesion(base_de_datos):
    with base_de_datos() as s:
        yield s


@pytest.fixture
def como(base_de_datos, credenciales):
    """Fábrica de clientes HTTP con la sesión iniciada para el rol indicado."""
    from fastapi.testclient import TestClient

    from app.core.reloj import obtener_reloj
    from app.main import app

    app.dependency_overrides[obtener_reloj] = lambda: (lambda: AHORA_FIJO)
    abiertos = []

    def _cliente(clave: str | None = None) -> TestClient:
        c = TestClient(app)
        c.__enter__()
        abiertos.append(c)
        if clave:
            nombre, contrasena = credenciales[clave]
            r = c.post("/api/v1/auth/ingreso",
                       json={"nombre_usuario": nombre, "contrasena": contrasena})
            assert r.status_code == 200, r.text
        return c

    yield _cliente
    for c in abiertos:
        c.__exit__(None, None, None)
    app.dependency_overrides.clear()


class RelojMovil:
    """Reloj que la prueba puede adelantar (vencimiento de tokens y fin del bloqueo)."""

    def __init__(self) -> None:
        self.momento = AHORA_FIJO

    def __call__(self) -> datetime:
        return self.momento

    def adelantar(self, **duracion) -> None:
        self.momento = self.momento + timedelta(**duracion)


@pytest.fixture
def reloj_movil(base_de_datos):
    """Cliente HTTP sin sesión cuyo reloj del servidor la prueba puede adelantar."""
    from fastapi.testclient import TestClient

    from app.core.reloj import obtener_reloj
    from app.main import app

    reloj = RelojMovil()
    app.dependency_overrides[obtener_reloj] = lambda: reloj
    with TestClient(app) as c:
        yield c, reloj
    app.dependency_overrides.clear()


@pytest.fixture
def nuevo_usuario(base_de_datos):
    """Crea un usuario propio de la prueba (para no alterar a los usuarios compartidos)."""
    from sqlalchemy import select

    from app.modelos.catalogos import Rol, UnidadOrganica
    from app.modelos.seguridad import Usuario
    from app.seguridad import contrasenas

    def _crear(rol: str = "AU", sigla: str | None = "GDUR",
               temporal: bool = False) -> tuple[str, str, int]:
        nombre = f"prueba.{secrets.token_hex(4)}"
        contrasena = secrets.token_urlsafe(18)
        with base_de_datos() as sesion:
            usuario = Usuario(
                nombre_usuario=nombre, nombres_apellidos="Usuario de prueba",
                id_rol=sesion.scalar(select(Rol.id_rol).where(Rol.codigo == rol)),
                id_unidad=sesion.scalar(select(UnidadOrganica.id_unidad)
                                        .where(UnidadOrganica.sigla == sigla)) if sigla else None,
                hash_contrasena=contrasenas.hashear(contrasena), contrasena_temporal=temporal,
                intentos_fallidos=0, estado="ACTIVO")
            sesion.add(usuario)
            sesion.commit()
            return nombre, contrasena, usuario.id_usuario

    return _crear


@pytest.fixture
def cliente(como):
    """Cliente con la sesión del Área Usuaria de la unidad GDUR."""
    return como("AU")


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
