"""Pruebas de integración del registro y la consulta del requerimiento. CP-I01 a CP-I10.

Integran DTO, seguridad, servicio, repositorios y base de datos para cumplir el RF-01 a RF-03.
"""

from sqlalchemy import func, select

from app.modelos.requerimiento import HistorialEtapa, Requerimiento, ValidacionPresupuestal
from app.seguridad.dependencias import UsuarioActual, usuario_actual


def test_cpi01_registro_con_saldo_suficiente_devuelve_201_verde(cliente, cuerpo_base, sesion):
    respuesta = cliente.post("/api/v1/requerimientos", json=cuerpo_base)
    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["monto_estimado"] == "12750.00"
    assert (datos["estado_semaforo"], datos["motivo"]) == ("VERDE", "DISPONIBLE")
    assert datos["codigo"].startswith("REQ-2026-")
    # RI-15: el historial y la validación se crearon en la misma transacción
    rid = datos["requerimiento_id"]
    assert sesion.scalar(select(func.count()).select_from(HistorialEtapa)
                         .where(HistorialEtapa.id_requerimiento == rid)) == 1
    assert sesion.scalar(select(func.count()).select_from(ValidacionPresupuestal)
                         .where(ValidacionPresupuestal.id_requerimiento == rid)) == 1


def test_cpi02_saldo_insuficiente_responde_201_rojo_con_opciones(cliente, cuerpo_base):
    cuerpo_base["items"].append({"descripcion": "Imprimante asfáltico", "unidad_medida": "galón",
                                 "cantidad": "300", "precio_unitario_ref": "95.00",
                                 "fuente_precio": "COMPRA_ANTERIOR"})
    datos = cliente.post("/api/v1/requerimientos", json=cuerpo_base).json()
    assert datos["estado_semaforo"] == "ROJO"
    assert datos["opciones_ajuste"] == ["REFORMULAR", "REPROGRAMAR"]
    assert datos["saldo_disponible_meta"] == "31500.00"


def test_cpi03_sin_item_del_pac_y_meta_sin_saldo_dan_ambar(cliente, cuerpo_base):
    cuerpo_base["pac_item_referencia"] = None
    assert cliente.post("/api/v1/requerimientos", json=cuerpo_base).json()["motivo"] == (
        "NO_PREVISTO_PAC")
    cuerpo_base["meta_codigo"] = "0033"
    assert cliente.post("/api/v1/requerimientos", json=cuerpo_base).json()["motivo"] == (
        "SIN_DATOS_META")


def test_cpi04_monto_mayor_a_8_uit_se_rechaza_sin_guardar_nada(cliente, cuerpo_base, sesion):
    antes = sesion.scalar(select(func.count()).select_from(Requerimiento))
    cuerpo_base["items"][0]["cantidad"] = "2000"  # S/ 85 000
    respuesta = cliente.post("/api/v1/requerimientos", json=cuerpo_base)
    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    assert sesion.scalar(select(func.count()).select_from(Requerimiento)) == antes


def test_cpi05_datos_mal_formados_se_rechazan_en_la_frontera(cliente, cuerpo_base):
    cuerpo_base["items"] = []
    cuerpo_base["objeto_contratacion"] = "OBRA"
    respuesta = cliente.post("/api/v1/requerimientos", json=cuerpo_base)
    assert respuesta.status_code == 422
    campos = {e["campo"] for e in respuesta.json()["errores"]}
    assert {"items", "objeto_contratacion"} <= campos


def test_cpi06_meta_inexistente_pac_inexistente_y_fecha_pasada(cliente, cuerpo_base):
    for cambio, mensaje in [({"meta_codigo": "9999"}, "meta"),
                            ({"pac_item_referencia": "PAC-999"}, "PAC"),
                            ({"fecha_necesidad": "2026-10-01"}, "fecha")]:
        respuesta = cliente.post("/api/v1/requerimientos", json={**cuerpo_base, **cambio})
        assert respuesta.status_code == 422
        assert mensaje in respuesta.json()["detail"]


def test_cpi07_detalle_muestra_etapas_responsable_y_base_de_calculo(cliente, cuerpo_base):
    rid = cliente.post("/api/v1/requerimientos", json=cuerpo_base).json()["requerimiento_id"]
    detalle = cliente.get(f"/api/v1/requerimientos/{rid}").json()
    assert [e["codigo"] for e in detalle["etapas"]][0] == "REGISTRADO"
    assert detalle["etapas"][0]["cumplida"] and detalle["etapas"][0]["actual"]
    assert detalle["responsable_actual"] == "Gerencia de Administración"
    assert detalle["semaforo"]["base_calculo"]["pim"] == "180000.00"


def test_cpi08_otra_unidad_no_puede_ver_el_requerimiento(cliente, cuerpo_base):
    from app.main import app

    rid = cliente.post("/api/v1/requerimientos", json=cuerpo_base).json()["requerimiento_id"]
    original = app.dependency_overrides.copy()
    app.dependency_overrides[usuario_actual] = lambda: UsuarioActual(None, 1, "AU", 9999)
    try:
        assert cliente.get(f"/api/v1/requerimientos/{rid}").status_code == 404
    finally:
        app.dependency_overrides = original


def test_cpi09_metas_y_pac_para_la_pantalla_p03(cliente):
    metas = {m["codigo"]: m for m in cliente.get("/api/v1/metas").json()}
    assert metas["0012"]["saldo_disponible"] == "31500.00"
    assert metas["0033"]["saldo_disponible"] is None
    assert len(cliente.get("/api/v1/pac-items").json()) == 5
    regla = cliente.get("/api/v1/regla-vigente").json()
    assert regla["tope_8_uit"] == "44000.00"


def test_cpi10_rol_no_autorizado_recibe_403(cliente):
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[usuario_actual] = lambda: UsuarioActual(None, 4, "JP", None)
    try:
        assert cliente.get("/api/v1/metas").status_code == 403
    finally:
        app.dependency_overrides = original
