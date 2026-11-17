"""Pruebas de integración del incremento 4A: tablero de visibilidad (P06), reglas del semáforo
(P14) y base presupuestal con carga CSV de respaldo (P15). CP-I58 a CP-I64.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select, update

from app.core.reloj import obtener_reloj
from app.main import app
from app.modelos.configuracion import ReglaSemaforo
from app.modelos.presupuesto import CargaDatos, MetaPresupuestal
from app.modelos.requerimiento import ValidacionPresupuestal
from app.modelos.seguridad import Bitacora
from tests.integracion.conftest import AHORA_FIJO
from tests.integracion.test_tramite import _enviar, _item, _registrar, _rojo

TABLERO = "/api/v1/tablero"
REGLAS = "/api/v1/reglas"
BASE = "/api/v1/base-presupuestal"


def _reloj_en(momento: datetime) -> None:
    """Cambia la hora del servidor; los clientes creados después inician sesión a esa hora."""
    app.dependency_overrides[obtener_reloj] = lambda: (lambda: momento)


def _todas_las_filas(c, **params):
    filas, pagina = [], 1
    while True:
        r = c.get(TABLERO, params={**params, "pagina": pagina})
        assert r.status_code == 200, r.text
        cuerpo = r.json()
        filas += cuerpo["filas"]
        if pagina >= cuerpo["paginas"]:
            return filas, cuerpo
        pagina += 1


# --- P06. Tablero de visibilidad ----------------------------------------------------------
def test_cpi58_tablero_por_rol_con_saldo_y_filtros(como, cuerpo_base):
    au, au2, ga = como("AU"), como("AU2"), como("GA")
    rojo = _registrar(au, _rojo(cuerpo_base))
    verde = _registrar(au, cuerpo_base)

    filas, cuerpo = _todas_las_filas(au)
    assert cuerpo["unidad"].endswith("(GDUR)")
    assert {f["unidad_sigla"] for f in filas} == {"GDUR"}  # solo su unidad
    fila_verde = next(f for f in filas if f["requerimiento_id"] == verde)
    assert fila_verde["saldo_disponible"] == "31500.00"  # PIM 180 000 − compromiso 148 500
    assert fila_verde["horas_en_etapa"] is None  # sin enviar: el plazo de la Gerencia no corre
    assert cuerpo["fecha_corte_mef"] is not None and cuerpo["por_pagina"] == 20
    assert all(f["requerimiento_id"] not in (rojo, verde) for f in _todas_las_filas(au2)[0])

    codigo_rojo = next(f["codigo"] for f in filas if f["requerimiento_id"] == rojo)
    solo = ga.get(TABLERO, params={"buscar": codigo_rojo}).json()
    assert [f["requerimiento_id"] for f in solo["filas"]] == [rojo]
    assert solo["unidad"] is None and solo["tarjetas"]["rojo"] >= 1
    assert all(f["semaforo_vigente"] == "ROJO" and f["estado_codigo"] != "OBSERVADO"
               for f in _todas_las_filas(ga, semaforo="ROJO")[0])
    assert {f["meta_codigo"] for f in _todas_las_filas(ga, meta="0015")[0]} == {"0015"}
    montos = [float(f["monto_estimado"]) for f in
              ga.get(TABLERO, params={"orden": "monto", "descendente": True}).json()["filas"]]
    assert montos == sorted(montos, reverse=True)
    assert ga.get(TABLERO, params={"pagina": 999}).json()["pagina"] >= 1


def test_cpi59_tablero_resalta_el_cuello_de_botella_y_niega_otros_roles(como, cuerpo_base):
    au = como("AU")
    enviado = _registrar(au, cuerpo_base)
    _enviar(au, enviado)  # Registrado y enviado: plazo de 24 h de la Gerencia (Tabla 14)
    assert como("ADM").get(TABLERO).status_code == 403
    assert como("JL").get(TABLERO).status_code == 200
    assert como("AU").get(TABLERO, params={"semaforo": "AZUL"}).status_code == 422

    _reloj_en(AHORA_FIJO + timedelta(hours=30))
    filas, cuerpo = _todas_las_filas(como("GA"), cuello_de_botella=True)
    fila = next(f for f in filas if f["requerimiento_id"] == enviado)
    assert fila["cuello_de_botella"] is True and fila["horas_en_etapa"] == 30.0
    assert fila["plazo_horas"] == 24 and all(f["cuello_de_botella"] for f in filas)
    assert cuerpo["tarjetas"]["cuello_de_botella"] >= 1
    _reloj_en(AHORA_FIJO)


# --- P14. Configurar reglas del semáforo --------------------------------------------------
def test_cpi60_reglas_solo_presupuesto_rangos_y_sin_cambios(como):
    for rol in ("AU", "GA", "JL", "ADM"):
        assert como(rol).get(REGLAS).status_code == 403
    jp = como("JP")
    reglas = jp.get(REGLAS).json()
    assert reglas["parametros"]["valor_uit"] == "5500.00"
    assert reglas["historial"][-1]["registrado_por"] == "Carga inicial del sistema"
    fuera = {**reglas["parametros"], "umbral_disponibilidad_pct": 250}
    assert jp.post(REGLAS, json=fuera).status_code == 422
    igual = jp.post(REGLAS, json=reglas["parametros"])
    assert igual.status_code == 409 and "iguales" in igual.json()["detail"]


def test_cpi61_nueva_version_rige_desde_ya_y_conserva_las_anteriores(como, cuerpo_base,
                                                                    sesion):
    # La regla inicial se registró con la hora real de la base de datos; para trabajar con el
    # reloj fijo de las pruebas se la fecha un día antes (RI-10: la nueva debe ser posterior).
    sesion.execute(update(ReglaSemaforo).where(ReglaSemaforo.vigente_hasta.is_(None))
                   .values(vigente_desde=AHORA_FIJO - timedelta(days=1)))
    sesion.commit()
    jp, au = como("JP"), como("AU")
    anterior = jp.get(REGLAS).json()
    id_anterior = anterior["id_regla"]
    validaciones_previas = sesion.scalar(
        select(func.count()).select_from(ValidacionPresupuestal)
        .where(ValidacionPresupuestal.id_regla == id_anterior))
    nueva = {**anterior["parametros"], "valor_uit": "5350.00", "antiguedad_maxima_dias": 5}
    r = jp.post(REGLAS, json=nueva)
    assert r.status_code == 201, r.text
    reglas = r.json()
    assert reglas["id_regla"] != id_anterior and reglas["parametros"]["valor_uit"] == "5350.00"
    cambios = {c["parametro"]: (c["anterior"], c["nuevo"])
               for c in reglas["historial"][0]["cambios"]}
    assert cambios == {"valor_uit": ("5500.00", "5350.00"), "antiguedad_maxima_dias": ("7", "5")}
    assert reglas["historial"][1]["vigente_hasta"] is not None  # la anterior queda cerrada

    # El tope de 8 UIT ahora es S/ 42 800: un pedido de S/ 43 000 ya no se puede registrar.
    caro = {**cuerpo_base, "items": [_item("Asfalto en frío", 1000, 43)]}
    rechazo = au.post("/api/v1/requerimientos", json=caro)
    assert rechazo.status_code == 422 and "42,800.00" in rechazo.json()["detail"]
    sesion.expire_all()
    assert sesion.scalar(select(func.count()).select_from(ReglaSemaforo)
                         .where(ReglaSemaforo.vigente_hasta.is_(None))) == 1  # I-14
    assert sesion.scalar(select(func.count()).select_from(ValidacionPresupuestal).where(
        ValidacionPresupuestal.id_regla == id_anterior)) == validaciones_previas  # R14
    registro = sesion.scalar(select(Bitacora).where(Bitacora.accion == "CONFIG_REGLA")
                             .order_by(Bitacora.id_bitacora.desc()).limit(1))
    assert registro.recurso_id == reglas["id_regla"]
    assert registro.detalle["cambios"]["valor_uit"] == {"anterior": "5500.00",
                                                        "nuevo": "5350.00"}

    # Se restituye la regla inicial para las demás pruebas (otra versión, un minuto después).
    _reloj_en(AHORA_FIJO + timedelta(minutes=1))
    assert como("JP").post(REGLAS, json=anterior["parametros"]).status_code == 201
    _reloj_en(AHORA_FIJO)


# --- P15. Base presupuestal y carga CSV de respaldo ---------------------------------------
MEF_2025 = ("meta_codigo,meta_nombre,pim,certificacion,compromiso_anual\n"
            "0101,Meta de prueba A,50000.00,30000.00,20000.00\n"
            "0102,Meta de prueba B,\"1,000.00\",500.00,100.00\n")


def _carga(fuente, contenido, corte="2025-12-31", anio=2025):
    return {"fuente": fuente, "anio_fiscal": anio, "fecha_corte": corte, "contenido": contenido}


def test_cpi62_estado_de_la_base_y_vista_previa_sin_escribir(como, sesion):
    for rol in ("AU", "GA", "JL", "ADM"):
        assert como(rol).get(BASE).status_code == 403
    jp = como("JP")
    estado = jp.get(BASE).json()
    mef = next(f for f in estado["fuentes"] if f["fuente"] == "MEF")
    assert mef["ultima_exitosa"]["origen"] == "MANUAL_CSV" and mef["desactualizado"] is False
    assert mef["dias_desde_corte"] == 1 and estado["columnas"]["SEACE"][0] == "numero_referencia"

    cargas = sesion.scalar(select(func.count()).select_from(CargaDatos))
    con_error = ("meta_codigo,meta_nombre,pim,certificacion,compromiso_anual\n"
                 "0101,Meta A,1000,2000,100\n0102,Meta B,-5,0,0\n")
    previa = jp.post(f"{BASE}/validacion", json=_carga("MEF", con_error)).json()
    assert previa["valido"] is False and previa["total_errores"] == 2
    assert previa["errores"][0].startswith("Fila 2") and "Fila 3" in previa["errores"][1]
    sin_columnas = jp.post(f"{BASE}/validacion", json=_carga("SEACE", "a,b\n1,2\n")).json()
    assert not sin_columnas["valido"] and "Faltan las columnas" in sin_columnas["errores"][0]
    assert jp.post(f"{BASE}/validacion",
                   json=_carga("MEF", MEF_2025, corte="2026-10-26", anio=2026)).status_code == 422
    assert jp.post(f"{BASE}/validacion",
                   json=_carga("MEF", MEF_2025, anio=2027)).status_code == 422
    assert jp.post(f"{BASE}/validacion",
                   json=_carga("MEF", MEF_2025, corte="2024-12-31")).status_code == 422

    previa = jp.post(f"{BASE}/validacion", json=_carga("MEF", MEF_2025)).json()
    assert previa["valido"] is True and previa["total_filas"] == 2
    assert previa["vista_previa"][1]["pim"] == "1000.00"
    assert any("más de 7 días" in a for a in previa["avisos"])
    assert any("2 meta(s) nueva(s)" in a for a in previa["avisos"])
    sesion.expire_all()
    assert sesion.scalar(select(func.count()).select_from(CargaDatos)) == cargas  # nada escrito


def test_cpi63_carga_vigente_y_carga_con_corte_anterior(como, sesion):
    jp = como("JP")
    r = jp.post(f"{BASE}/cargas", json=_carga("MEF", MEF_2025))
    assert r.status_code == 201, r.text
    assert r.json()["filas"] == 2 and r.json()["vigente"] is True
    id_carga = r.json()["carga"]["id_carga"]
    registro = sesion.scalar(select(Bitacora).where(Bitacora.accion == "EXTRACCION_DATOS")
                             .order_by(Bitacora.id_bitacora.desc()).limit(1))
    assert registro.recurso_id == id_carga and registro.detalle["filas"] == 2

    def activas():
        sesion.expire_all()
        return {m.codigo for m in sesion.scalars(select(MetaPresupuestal).where(
            MetaPresupuestal.anio_fiscal == 2025, MetaPresupuestal.activa.is_(True)))}

    assert activas() == {"0101", "0102"}
    solo_a = "meta_codigo,meta_nombre,pim,certificacion,compromiso_anual\n0101,Meta A,1,1,1\n"
    # Con un corte anterior queda en el historial, pero no cambia la base vigente.
    previa = jp.post(f"{BASE}/validacion", json=_carga("MEF", solo_a, corte="2025-12-30")).json()
    assert any("anterior a la de la carga vigente" in a for a in previa["avisos"])
    antigua = jp.post(f"{BASE}/cargas", json=_carga("MEF", solo_a, corte="2025-12-30")).json()
    assert antigua["vigente"] is False and activas() == {"0101", "0102"}
    # Con un corte posterior pasa a ser la vigente: la meta que no figura deja de ofrecerse.
    previa = jp.post(f"{BASE}/validacion", json=_carga("MEF", solo_a, corte="2026-01-15")).json()
    assert any("dejarán de ofrecerse" in a and "0102" in a for a in previa["avisos"])
    nueva = jp.post(f"{BASE}/cargas", json=_carga("MEF", solo_a, corte="2026-01-15")).json()
    assert nueva["vigente"] is True and activas() == {"0101"}

    pac = ("numero_referencia,descripcion,tipo_objeto,valor_estimado\n"
           "PAC-2025-01,Adquisición de cemento,BIEN,8000.00\n")
    assert jp.post(f"{BASE}/cargas", json=_carga("SEACE", pac)).json()["filas"] == 1


def test_cpi64_carga_rechazada_y_dato_desactualizado(como, sesion):
    jp = como("JP")
    mal = "meta_codigo,meta_nombre,pim,certificacion,compromiso_anual\n0103,Meta C,10,20,5\n"
    r = jp.post(f"{BASE}/cargas", json=_carga("MEF", mal))
    assert r.status_code == 422 and r.json()["errores_archivo"]
    rechazada = sesion.get(CargaDatos, r.json()["id_carga"])
    assert rechazada.resultado == "RECHAZADA" and rechazada.fecha_corte is None
    historial = jp.get(BASE).json()["historial"]
    assert rechazada.id_carga in [h["id_carga"] for h in historial]
    vacio = {**_carga("MEF", mal), "contenido": ""}
    assert jp.post(f"{BASE}/cargas", json=vacio).status_code == 422

    # Diez días después del corte del MEF (24/10), el dato vigente ya está desactualizado.
    _reloj_en(AHORA_FIJO + timedelta(days=10))
    mef = next(f for f in como("JP").get(BASE).json()["fuentes"] if f["fuente"] == "MEF")
    assert mef["desactualizado"] is True and mef["dias_desde_corte"] == 11
    _reloj_en(AHORA_FIJO)
