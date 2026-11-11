"""Pruebas de integración del trámite: Área Usuaria, Gerencia y alertas de Presupuesto.

CP-I37 a CP-I49 (incremento 3, parte A): máquina de estados con rol por transición, P05
(ajuste y RI-26), P08 (bandeja), P11 (decisión sobre el ámbar), P17, P07 y P02.
"""

from sqlalchemy import select

from app.modelos.requerimiento import AjusteRequerimiento, ValidacionPresupuestal
from app.modelos.seguridad import Bitacora

DOCUMENTOS_OK = {"documento_requerimiento_firmado": True, "cuadro_necesidades": True,
                 "especificaciones_tecnicas_tdr": True}


def _item(descripcion, cantidad, precio, unidad="unidad"):
    return {"descripcion": descripcion, "unidad_medida": unidad, "cantidad": str(cantidad),
            "precio_unitario_ref": str(precio), "fuente_precio": "COTIZACION"}


def _registrar(c, cuerpo):
    r = c.post("/api/v1/requerimientos", json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()["requerimiento_id"]


def _enviar(c, rid):
    detalle = c.get(f"/api/v1/requerimientos/{rid}").json()
    cuerpo = {"items": [{"id_item": i["id_item"], "especificacion": "Según ficha técnica"}
                        for i in detalle["items"]],
              "plazo_entrega_dias": 10, "lugar_entrega": "Almacén central",
              "documentos": DOCUMENTOS_OK}
    r = c.post(f"/api/v1/requerimientos/{rid}/envio", json=cuerpo)
    assert r.status_code == 200, r.text


def _etapa(c, rid, destino, observacion=None):
    return c.patch(f"/api/v1/requerimientos/{rid}/etapa",
                   json={"destino": destino, "observacion": observacion})


def _rojo(cuerpo_base):
    """Meta 0015: saldo disponible de S/ 2,400.00; S/ 3,500.00 resulta en rojo."""
    return {**cuerpo_base, "meta_codigo": "0015", "pac_item_referencia": "PAC-003",
            "objeto_contratacion": "SERVICIO", "descripcion": "Mantenimiento de jardines",
            "items": [_item("Poda de árboles", 10, 300), _item("Abono orgánico", 5, 100, "saco")]}


def _ambar(cuerpo_base):
    """Meta 0033: sin saldo en la base presupuestal (SIN_DATOS_META)."""
    return {**cuerpo_base, "meta_codigo": "0033", "pac_item_referencia": None,
            "descripcion": "Chalecos reflectivos para serenazgo",
            "items": [_item("Chaleco reflectivo", 20, 45)]}


def test_cpi37_gerencia_aprueba_un_verde_enviado(como, cuerpo_base, sesion):
    au, ga = como("AU"), como("GA")
    rid = _registrar(au, cuerpo_base)
    _enviar(au, rid)
    assert any(f["requerimiento_id"] == rid for f in ga.get("/api/v1/bandeja").json())
    r = _etapa(ga, rid, "APROBADO", "Procede. Derivar a Abastecimientos.")
    assert r.status_code == 200, r.text
    assert r.json()["estado_anterior"] == "Registrado" and r.json()["estado_actual"] == "Aprobado"
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["estado_actual"] == "Aprobado"
    assert detalle["responsable_actual"] == "Jefe de Logística y Abastecimientos"
    assert not any(f["requerimiento_id"] == rid for f in ga.get("/api/v1/bandeja").json())
    cambio = sesion.scalar(select(Bitacora).where(
        Bitacora.accion == "CAMBIO_ETAPA", Bitacora.recurso_id == rid))
    assert cambio.detalle == {"origen": "REGISTRADO", "destino": "APROBADO", "tipo": "AVANCE"}


def test_cpi38_rol_por_transicion_y_guardas_de_la_gerencia(como, cuerpo_base, sesion):
    au, ga, jl = como("AU"), como("GA"), como("JL")
    rid = _registrar(au, cuerpo_base)
    assert _etapa(ga, rid, "APROBADO").status_code == 409  # aún no se envía
    _enviar(au, rid)
    assert _etapa(au, rid, "APROBADO").status_code == 403  # le corresponde a la Gerencia
    assert _etapa(jl, rid, "APROBADO").status_code == 403
    assert _etapa(ga, rid, "CERTIFICADO").status_code == 409  # transición inexistente
    denegado = sesion.scalar(select(Bitacora).where(
        Bitacora.accion == "ACCESO_DENEGADO", Bitacora.recurso_id == rid))
    assert denegado.detalle["motivo"] == "rol_por_transicion"
    roja = _registrar(au, _rojo(cuerpo_base))
    assert _etapa(ga, roja, "APROBADO").status_code == 409  # la Gerencia solo ve verdes


def test_cpi39_observar_y_subsanar_vuelve_a_la_bandeja(como, cuerpo_base):
    au, ga = como("AU"), como("GA")
    rid = _registrar(au, cuerpo_base)
    _enviar(au, rid)
    assert _etapa(ga, rid, "OBSERVADO").status_code == 422  # observación obligatoria
    assert _etapa(ga, rid, "OBSERVADO", "Falta la firma del jefe del área.").status_code == 200
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["observacion_recibida"]["texto"] == "Falta la firma del jefe del área."
    assert detalle["observacion_recibida"]["rol"] == "Gerencia de Administración"
    assert detalle["acciones"]["subsanar"] and not detalle["acciones"]["anular"]
    inicio = au.get("/api/v1/inicio").json()
    assert any(p["requerimiento_id"] == rid and p["accion"] == "Revisar y subsanar"
               for p in inicio["pendientes"])
    assert _etapa(au, rid, "REGISTRADO", "Se adjunta el documento firmado.").status_code == 200
    assert any(f["requerimiento_id"] == rid for f in ga.get("/api/v1/bandeja").json())


def test_cpi40_reformular_reduce_y_quita_items_y_revalida(como, cuerpo_base, sesion):
    au = como("AU")
    rid = _registrar(au, _rojo(cuerpo_base))
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["semaforo_vigente"] == "ROJO" and detalle["acciones"]["aplicar_ajuste"]
    poda = detalle["items"][0]["id_item"]
    r = au.post(f"/api/v1/requerimientos/{rid}/ajustes", json={
        "opcion": "REFORMULAR", "items": [{"id_item_original": poda, "cantidad": "6"}]})
    assert r.status_code == 200, r.text
    resultado = r.json()
    assert resultado["monto_estimado"] == "1800.00" and resultado["revalidado"]
    assert resultado["estado_semaforo"] == "VERDE"
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert len(detalle["items"]) == 1 and detalle["opcion_ajuste"] is None  # nueva validación
    assert detalle["puede_completar_paso_2"]
    ajuste = sesion.scalar(select(AjusteRequerimiento).join(
        ValidacionPresupuestal,
        ValidacionPresupuestal.id_validacion == AjusteRequerimiento.id_validacion).where(
        ValidacionPresupuestal.id_requerimiento == rid))
    assert ajuste.opcion == "REFORMULAR" and str(ajuste.monto_nuevo) == "1800.00"
    registro = sesion.scalar(select(Bitacora).where(
        Bitacora.accion == "AJUSTE_REQUERIMIENTO", Bitacora.recurso_id == rid))
    assert len(registro.detalle["items_anteriores"]) == 2
    assert registro.detalle["monto_anterior"] == "3500.00"
    # Ya no está en rojo: no admite otro ajuste.
    assert au.post(f"/api/v1/requerimientos/{rid}/ajustes",
                   json={"opcion": "NINGUNA"}).status_code == 409


def test_cpi41_ri26_bloquea_el_precio_y_exige_un_cambio_real(como, cuerpo_base):
    au = como("AU")
    rid = _registrar(au, _rojo(cuerpo_base))
    items = au.get(f"/api/v1/requerimientos/{rid}").json()["items"]
    poda, abono = items[0]["id_item"], items[1]["id_item"]
    url = f"/api/v1/requerimientos/{rid}/ajustes"
    bajar_precio = au.post(url, json={"opcion": "REFORMULAR", "items": [
        {"id_item_original": poda, "cantidad": "10", "precio_unitario_ref": "150.00"},
        {"id_item_original": abono, "cantidad": "5"}]})
    assert bajar_precio.status_code == 422 and "RI-26" in bajar_precio.json()["detail"]
    subir = au.post(url, json={"opcion": "REFORMULAR", "items": [
        {"id_item_original": poda, "cantidad": "12"}]})
    assert subir.status_code == 422 and "solo puede reducirse" in subir.json()["detail"]
    igual = au.post(url, json={"opcion": "REFORMULAR", "items": [
        {"id_item_original": poda, "cantidad": "10"},
        {"id_item_original": abono, "cantidad": "5"}]})
    assert igual.status_code == 422
    incompleto = au.post(url, json={"opcion": "REFORMULAR", "items": [{"cantidad": "1"}]})
    assert incompleto.status_code == 422
    # Reemplazar un ítem por otro de distinta especificación, con su propio precio, sí procede.
    reemplazo = au.post(url, json={"opcion": "REFORMULAR", "items": [
        {"id_item_original": abono, "cantidad": "5"},
        {"cantidad": "10", "descripcion": "Poda de arbustos", "unidad_medida": "unidad",
         "precio_unitario_ref": "150.00", "fuente_precio": "COMPRA_ANTERIOR"}]})
    assert reemplazo.status_code == 200, reemplazo.text
    assert reemplazo.json()["monto_estimado"] == "2000.00"


def test_cpi42_reprogramar_ninguna_y_anular(como, cuerpo_base):
    au = como("AU")
    rid = _registrar(au, _rojo(cuerpo_base))
    url = f"/api/v1/requerimientos/{rid}/ajustes"
    assert au.post(url, json={"opcion": "REPROGRAMAR",
                              "fecha_necesidad_nueva": "2026-11-10"}).status_code == 422
    assert _etapa(au, rid, "ANULADO").status_code == 409  # aún tiene opciones de ajuste
    r = au.post(url, json={"opcion": "REPROGRAMAR", "fecha_necesidad_nueva": "2026-12-15"})
    assert r.status_code == 200 and r.json()["estado_semaforo"] == "ROJO"
    assert r.json()["fecha_necesidad"] == "2026-12-15"
    # La nueva validación sigue en rojo: el área puede rechazar las opciones y anular.
    assert au.post(url, json={"opcion": "NINGUNA"}).json()["revalidado"] is False
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["acciones"]["anular"]
    assert detalle["accion_pendiente"] == "Anular el requerimiento"
    assert _etapa(au, rid, "ANULADO", "Sin presupuesto en el ejercicio.").status_code == 200
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["estado_actual"] == "Anulado" and detalle["responsable_actual"] == "—"
    assert not any(p["requerimiento_id"] == rid
                   for p in au.get("/api/v1/inicio").json()["pendientes"])


def test_cpi43_presupuesto_confirma_un_ambar_y_pasa_a_verde(como, cuerpo_base, sesion):
    au, jp = como("AU"), como("JP")
    rid = _registrar(au, _ambar(cuerpo_base))
    alertas = jp.get("/api/v1/alertas").json()
    fila = next(a for a in alertas["ambar"] if a["requerimiento_id"] == rid)
    assert fila["motivo"] == "SIN_DATOS_META" and fila["fecha_corte"] is None
    assert any(p["requerimiento_id"] == rid for p in jp.get("/api/v1/inicio").json()["pendientes"])
    url = f"/api/v1/alertas/{rid}/decision"
    assert au.post(url, json={"resultado": "CONFIRMADA"}).status_code == 403
    r = jp.post(url, json={"resultado": "CONFIRMADA", "sustento": "Hay saldo en la meta 0033."})
    assert r.status_code == 200 and r.json()["semaforo_vigente"] == "VERDE"
    assert jp.post(url, json={"resultado": "DENEGADA", "sustento": "x"}).status_code == 409
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["confirmado_por_presupuesto"] and detalle["puede_completar_paso_2"]
    assert detalle["decision_presupuesto"]["rol"] == "Jefe de Presupuesto"
    assert not any(a["requerimiento_id"] == rid for a in jp.get("/api/v1/alertas").json()["ambar"])
    registro = sesion.scalar(select(Bitacora).where(
        Bitacora.accion == "DECISION_AMBAR", Bitacora.recurso_id == rid))
    assert registro.detalle["resultado"] == "CONFIRMADA"
    _enviar(au, rid)
    fila = next(f for f in como("GA").get("/api/v1/bandeja").json() if f["requerimiento_id"] == rid)
    assert fila["confirmado_por_presupuesto"]


def test_cpi44_ambar_denegado_exige_sustento_y_solo_queda_anular(como, cuerpo_base):
    au, jp = como("AU"), como("JP")
    rid = _registrar(au, _ambar(cuerpo_base))
    url = f"/api/v1/alertas/{rid}/decision"
    assert jp.post(url, json={"resultado": "DENEGADA"}).status_code == 422
    assert jp.post(url, json={"resultado": "DENEGADA",
                              "sustento": "La meta no tiene crédito."}).status_code == 200
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["semaforo_vigente"] == "AMBAR_DENEGADO" and detalle["acciones"]["anular"]
    assert not detalle["puede_completar_paso_2"]
    assert _etapa(au, rid, "ANULADO").status_code == 200


def test_cpi45_mis_requerimientos_filtra_y_solo_muestra_la_unidad(como, cuerpo_base):
    au, au2 = como("AU"), como("AU2")
    rojo = _registrar(au, _rojo(cuerpo_base))
    filas = au.get("/api/v1/requerimientos", params={"semaforo": "ROJO"}).json()
    fila = next(f for f in filas if f["requerimiento_id"] == rojo)
    assert fila["accion"] == "Aplicar ajuste"
    assert fila["destino"] == f"/requerimientos/ajuste?id={rojo}"
    assert all(f["semaforo_vigente"] == "ROJO" for f in filas)
    codigo = fila["codigo"]
    assert [f["codigo"] for f in au.get("/api/v1/requerimientos",
                                        params={"buscar": codigo}).json()] == [codigo]
    assert all(f["requerimiento_id"] != rojo for f in au2.get("/api/v1/requerimientos").json())
    assert au.get("/api/v1/requerimientos", params={"semaforo": "AZUL"}).status_code == 422
    assert como("GA").get("/api/v1/requerimientos").status_code == 403


def test_cpi46_historial_con_duracion_y_etapas_futuras(como, cuerpo_base):
    au, ga = como("AU"), como("GA")
    rid = _registrar(au, cuerpo_base)
    _enviar(au, rid)
    _etapa(ga, rid, "APROBADO", "Procede.")
    historial = ga.get(f"/api/v1/requerimientos/{rid}/historial").json()
    assert [r["estado"] for r in historial["registros"]] == ["Registrado", "Aprobado"]
    assert historial["registros"][0]["horas_en_etapa"] == 0.0
    assert historial["registros"][1]["en_curso"] and historial["registros"][1]["rol"] == \
        "Gerencia de Administración"
    assert historial["registros"][1]["observacion"] == "Procede."
    assert historial["etapas_futuras"][0]["estado_codigo"] == "DOCUMENTACION_VALIDADA"
    assert historial["horas_totales"] is None and not historial["cerrado"]
    assert "nombre" not in str(historial["registros"]).lower()  # solo roles, no personas
    assert como("AU2").get(f"/api/v1/requerimientos/{rid}/historial").status_code == 404
    assert como("JP").get(f"/api/v1/requerimientos/{rid}/historial").status_code == 200


def test_cpi47_otros_roles_ven_el_detalle_sin_acciones_del_area(como, cuerpo_base):
    au = como("AU")
    rid = _registrar(au, _rojo(cuerpo_base))
    for rol in ("GA", "JL", "JP"):
        detalle = como(rol).get(f"/api/v1/requerimientos/{rid}")
        assert detalle.status_code == 200
        assert not any(detalle.json()["acciones"].values())
    assert como("ADM").get(f"/api/v1/requerimientos/{rid}").status_code == 403
    assert como("GA").post(f"/api/v1/requerimientos/{rid}/ajustes",
                           json={"opcion": "NINGUNA"}).status_code == 403


def test_cpi48_inicio_de_la_gerencia_lista_su_bandeja(como, cuerpo_base):
    au, ga = como("AU"), como("GA")
    rid = _registrar(au, cuerpo_base)
    _enviar(au, rid)
    pendiente = next(p for p in ga.get("/api/v1/inicio").json()["pendientes"]
                     if p["requerimiento_id"] == rid)
    assert pendiente["accion"] == "Aprobar u observar"
    assert pendiente["destino"] == f"/bandeja?id={rid}"
