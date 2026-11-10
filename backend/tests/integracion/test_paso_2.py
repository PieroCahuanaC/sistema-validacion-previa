"""Pruebas de integración del registro en dos pasos (cambio 15 de la Práctica 7).

CP-I15 a CP-I21: guardar el paso 2, enviar a la Gerencia y las reglas RI-20 y RI-28.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

DOCUMENTOS_OK = {
    "documento_requerimiento_firmado": True,
    "cuadro_necesidades": True,
    "especificaciones_tecnicas_tdr": True,
}


def _registrar(cliente, cuerpo):
    return cliente.post("/api/v1/requerimientos", json=cuerpo).json()["requerimiento_id"]


def _paso_2_completo(cliente, rid):
    detalle = cliente.get(f"/api/v1/requerimientos/{rid}").json()
    return {
        "items": [{"id_item": i["id_item"], "especificacion": "Bolsa de 25 kg, curado en frío"}
                  for i in detalle["items"]],
        "plazo_entrega_dias": 10,
        "lugar_entrega": "Almacén central de la Municipalidad",
    }


def test_cpi15_guardar_paso_2_parcial_no_envia(cliente, cuerpo_base):
    rid = _registrar(cliente, cuerpo_base)
    r = cliente.put(f"/api/v1/requerimientos/{rid}/paso-2", json={"plazo_entrega_dias": 7})
    assert r.status_code == 200
    detalle = r.json()
    assert detalle["plazo_entrega_dias"] == 7 and detalle["lugar_entrega"] is None
    assert detalle["fecha_envio"] is None and detalle["puede_completar_paso_2"]


def test_cpi16_envio_completo_en_verde_pasa_a_la_gerencia(cliente, cuerpo_base):
    rid = _registrar(cliente, cuerpo_base)
    cuerpo = {**_paso_2_completo(cliente, rid), "documentos": DOCUMENTOS_OK}
    r = cliente.post(f"/api/v1/requerimientos/{rid}/envio", json=cuerpo)
    assert r.status_code == 200, r.text
    assert r.json()["fecha_envio"].startswith("2026-10-25")
    detalle = cliente.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["responsable_actual"] == "Gerencia de Administración"
    assert not detalle["puede_completar_paso_2"]
    assert detalle["items"][0]["especificacion"] == "Bolsa de 25 kg, curado en frío"


def test_cpi17_envio_sin_documentos_o_incompleto_se_rechaza_sin_guardar(cliente, cuerpo_base):
    rid = _registrar(cliente, cuerpo_base)
    sin_docs = {**_paso_2_completo(cliente, rid),
                "documentos": {**DOCUMENTOS_OK, "cuadro_necesidades": False}}
    r = cliente.post(f"/api/v1/requerimientos/{rid}/envio", json=sin_docs)
    assert r.status_code == 422 and "tres documentos" in r.json()["detail"]
    incompleto = {"items": [], "plazo_entrega_dias": 5, "documentos": DOCUMENTOS_OK}
    r = cliente.post(f"/api/v1/requerimientos/{rid}/envio", json=incompleto)
    assert r.status_code == 422
    assert "especificación" in r.json()["detail"] and "lugar" in r.json()["detail"]
    assert cliente.get(f"/api/v1/requerimientos/{rid}").json()["fecha_envio"] is None


def test_cpi18_paso_2_bloqueado_en_rojo_y_en_ambar_sin_decision(cliente, cuerpo_base):
    rojo = {**cuerpo_base, "items": [{**cuerpo_base["items"][0], "cantidad": "900"}]}
    ambar = {**cuerpo_base, "pac_item_referencia": None}
    for cuerpo in (rojo, ambar):
        rid = _registrar(cliente, cuerpo)
        assert not cliente.get(f"/api/v1/requerimientos/{rid}").json()["puede_completar_paso_2"]
        r = cliente.put(f"/api/v1/requerimientos/{rid}/paso-2", json={})
        assert r.status_code == 409 and "verde" in r.json()["detail"]


def test_cpi19_ambar_confirmado_por_presupuesto_habilita_el_paso_2(cliente, cuerpo_base, sesion):
    rid = _registrar(cliente, {**cuerpo_base, "pac_item_referencia": None})
    sesion.execute(text(
        "INSERT INTO decision_presupuesto (id_validacion, resultado, sustento) "
        "SELECT id_validacion, 'CONFIRMADA', 'Verificado en el SIAF' "
        "FROM validacion_presupuestal WHERE id_requerimiento = :r"), {"r": rid})
    sesion.commit()
    detalle = cliente.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["semaforo_vigente"] == "VERDE" and detalle["confirmado_por_presupuesto"]
    assert detalle["puede_completar_paso_2"]
    assert detalle["responsable_actual"] == "Área Usuaria"


def test_cpi20_no_se_envia_dos_veces_ni_se_edita_lo_enviado(cliente, cuerpo_base):
    rid = _registrar(cliente, cuerpo_base)
    cuerpo = {**_paso_2_completo(cliente, rid), "documentos": DOCUMENTOS_OK}
    assert cliente.post(f"/api/v1/requerimientos/{rid}/envio", json=cuerpo).status_code == 200
    assert cliente.post(f"/api/v1/requerimientos/{rid}/envio", json=cuerpo).status_code == 409
    r = cliente.put(f"/api/v1/requerimientos/{rid}/paso-2", json={"plazo_entrega_dias": 99})
    assert r.status_code == 409 and "ya fue enviado" in r.json()["detail"]


def test_cpi21_item_ajeno_se_rechaza_y_bd_exige_paso_2_para_enviar_ri28(
    cliente, cuerpo_base, sesion
):
    rid = _registrar(cliente, cuerpo_base)
    r = cliente.put(f"/api/v1/requerimientos/{rid}/paso-2",
                    json={"items": [{"id_item": 999999, "especificacion": "x"}]})
    assert r.status_code == 422
    with pytest.raises(DBAPIError, match="ri28_envio_con_paso_2"):
        sesion.execute(text("UPDATE requerimiento SET fecha_envio = now() "
                            "WHERE id_requerimiento = :r"), {"r": rid})
    sesion.rollback()
