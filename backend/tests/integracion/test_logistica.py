"""Pruebas de integración de Logística y certificación (incremento 3, parte B).

CP-I49 a CP-I57: validación documental (P09), cuadro comparativo con proveedores cifrados y
revalidación con el precio de mercado (P10), certificación (P12) y orden (P13), hasta el
cierre del trámite.
"""

from sqlalchemy import select

from app.modelos.logistica import CuadroComparativo, Proveedor
from app.modelos.seguridad import Bitacora
from tests.integracion.test_tramite import _ambar, _enviar, _etapa, _item, _registrar

PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def ruc(base: str) -> str:
    """Completa un RUC de 10 dígitos con su dígito verificador (módulo 11)."""
    resto = 11 - sum(int(d) * p for d, p in zip(base, PESOS, strict=True)) % 11
    return base + str({10: 0, 11: 1}.get(resto, resto))


def _hasta_aprobado(como, cuerpo):
    au, ga = como("AU"), como("GA")
    rid = _registrar(au, cuerpo)
    _enviar(au, rid)
    assert _etapa(ga, rid, "APROBADO", "Procede.").status_code == 200
    return rid


def _conforme(jl, rid):
    documentos = jl.get(f"/api/v1/requerimientos/{rid}/revision").json()["documentos"]
    r = jl.post(f"/api/v1/requerimientos/{rid}/revision", json={"documentos": [
        {"id_tipo_documento": d["id_tipo_documento"], "resultado": "CONFORME"}
        for d in documentos]})
    assert r.status_code == 200, r.text
    return r.json()


def _cuadro(precio, *cotizaciones, observacion=None):
    return {"cotizaciones": list(cotizaciones), "precio_referencia": str(precio),
            "observacion": observacion}


def _cot(monto, ruc_proveedor, tipo="JURIDICA", nombre="Distribuidora Andina S.A.C.",
         fecha="2026-10-20"):
    return {"proveedor": {"tipo_persona": tipo, "ruc": ruc_proveedor, "razon_social": nombre},
            "monto": str(monto), "fecha_cotizacion": fecha}


def test_cpi49_validacion_documental_conforme(como, cuerpo_base, sesion):
    jl = como("JL")
    rid = _hasta_aprobado(como, cuerpo_base)
    fila = next(f for f in jl.get("/api/v1/expedientes", params={"estado": "APROBADO"}).json()
                if f["requerimiento_id"] == rid)
    assert fila["estado_actual"] == "Aprobado"
    revision = jl.get(f"/api/v1/requerimientos/{rid}/revision").json()
    assert revision["puede_revisar"] and len(revision["documentos"]) == 3
    assert all(d["obligatorio"] for d in revision["documentos"])
    resultado = _conforme(jl, rid)
    assert resultado["resultado"] == "VALIDADA"
    assert resultado["estado_actual"] == "Documentación validada"
    pendiente = next(p for p in jl.get("/api/v1/inicio").json()["pendientes"]
                     if p["requerimiento_id"] == rid)
    assert pendiente["accion"] == "Registrar cuadro comparativo"
    assert pendiente["destino"] == f"/cuadro?id={rid}"
    registro = sesion.scalar(select(Bitacora).where(
        Bitacora.accion == "REVISION_DOCUMENTO", Bitacora.recurso_id == rid))
    assert set(registro.detalle["resultados"].values()) == {"CONFORME"}


def test_cpi50_documento_observado_devuelve_al_area_usuaria(como, cuerpo_base):
    au, jl = como("AU"), como("JL")
    rid = _hasta_aprobado(como, cuerpo_base)
    documentos = jl.get(f"/api/v1/requerimientos/{rid}/revision").json()["documentos"]
    url = f"/api/v1/requerimientos/{rid}/revision"
    sin_texto = [{"id_tipo_documento": d["id_tipo_documento"], "resultado": "CONFORME"}
                 for d in documentos]
    sin_texto[1]["resultado"] = "OBSERVADO"
    assert jl.post(url, json={"documentos": sin_texto}).status_code == 422  # RI-11
    assert jl.post(url, json={"documentos": sin_texto[:2]}).status_code == 422  # incompleto
    assert como("GA").post(url, json={"documentos": sin_texto}).status_code == 403
    sin_texto[1]["observacion"] = "Falta la firma del jefe del área."
    r = jl.post(url, json={"documentos": sin_texto})
    assert r.status_code == 200 and r.json()["resultado"] == "DEVUELTA"
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["estado_actual"] == "Observado"
    assert "Cuadro de necesidades: Falta la firma" in detalle["observacion_recibida"]["texto"]
    observada = [e["codigo"] for e in detalle["etapas"] if e["observada"]]
    assert observada == ["DOCUMENTACION_VALIDADA"]  # la etapa de Logística detuvo el trámite
    assert jl.post(url, json={"documentos": sin_texto}).status_code == 409  # ya no está Aprobado


def test_cpi51_cuadro_con_proveedor_natural_cifrado_pasa_a_presupuesto(
        como, cuerpo_base, sesion):
    jl, jp = como("JL"), como("JP")
    rid = _hasta_aprobado(como, cuerpo_base)
    _conforme(jl, rid)
    natural, juridica = ruc("1046779354"), ruc("2060012345")
    r = jl.put(f"/api/v1/requerimientos/{rid}/cuadro", json=_cuadro(
        "12500.00", _cot("12500.00", natural, "NATURAL", "Rosa Mamani Ccori"),
        _cot("13100.00", juridica), observacion="Se elige la menor cotización."))
    assert r.status_code == 200, r.text
    assert r.json()["revalidado"] is False and r.json()["destino"] == "PRESUPUESTO"
    assert r.json()["estado_actual"] == "Cuadro comparativo registrado"

    guardado = {p.tipo_persona: p for p in sesion.scalars(select(Proveedor))
                if p.tipo_persona == "JURIDICA" or "Rosa" not in p.razon_social}
    assert guardado["NATURAL"].ruc.startswith("v1:") and natural not in guardado["NATURAL"].ruc
    assert guardado["NATURAL"].razon_social.startswith("v1:")
    assert sesion.scalar(select(Proveedor).where(Proveedor.razon_social ==
                                                 "Distribuidora Andina S.A.C.")) is not None

    para_logistica = jl.get(f"/api/v1/requerimientos/{rid}/cuadro").json()
    nombres = {c["proveedor"]["razon_social"] for c in para_logistica["cotizaciones"]}
    assert "Rosa Mamani Ccori" in nombres and para_logistica["modo"] == "CONSULTA"
    assert para_logistica["menor_cotizacion"] == "12500.00"
    assert para_logistica["promedio"] == "12800.00"
    para_presupuesto = jp.get(f"/api/v1/requerimientos/{rid}/cuadro").json()
    assert all(c["proveedor"] is None for c in para_presupuesto["cotizaciones"])
    encontrado = jl.get("/api/v1/proveedores", params={"ruc": natural}).json()
    assert encontrado["encontrado"] and encontrado["proveedor"]["razon_social"] == \
        "Rosa Mamani Ccori"
    registro = sesion.scalar(select(Bitacora).where(
        Bitacora.accion == "REGISTRO_CUADRO", Bitacora.recurso_id == rid))
    assert "Rosa" not in str(registro.detalle) and natural not in str(registro.detalle)


def test_cpi52_validaciones_del_cuadro(como, cuerpo_base):
    jl = como("JL")
    rid = _hasta_aprobado(como, cuerpo_base)
    url = f"/api/v1/requerimientos/{rid}/cuadro"
    assert jl.put(url, json=_cuadro("100.00", _cot("100.00", ruc("2060012345")))).status_code \
        == 409  # la documentación aún no está validada
    _conforme(jl, rid)
    juridica = ruc("2060054321")
    invalido = juridica[:10] + str((int(juridica[10]) + 1) % 10)
    casos = [
        _cuadro("100.00"),  # sin cotizaciones
        _cuadro("100.00", _cot("100.00", invalido)),  # dígito verificador incorrecto
        _cuadro("100.00", _cot("100.00", ruc("2060077777"), "NATURAL", "Ana Rojas")),
        _cuadro("100.00", _cot("100.00", juridica), _cot("120.00", juridica)),  # repetido
        _cuadro("100.00", _cot("100.00", juridica, fecha="2026-12-31")),  # fecha futura
    ]
    for caso in casos:
        assert jl.put(url, json=caso).status_code == 422, caso
    assert como("JP").put(url, json=_cuadro("100.00", _cot("100.00", juridica))).status_code \
        == 403


def test_cpi53_precio_de_mercado_mayor_revalida_y_sigue_en_verde(como, cuerpo_base):
    jl = como("JL")
    rid = _hasta_aprobado(como, cuerpo_base)  # S/ 12,750.00; saldo de la meta S/ 31,500.00
    _conforme(jl, rid)
    r = jl.put(f"/api/v1/requerimientos/{rid}/cuadro",
               json=_cuadro("14000.00", _cot("14000.00", ruc("2060012345"))))
    assert r.json()["revalidado"] and r.json()["estado_semaforo"] == "VERDE"
    assert r.json()["destino"] == "PRESUPUESTO"
    detalle = jl.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["semaforo"]["base_calculo"]["monto_evaluado"] == "14000.00"


def test_cpi54_precio_de_mercado_sin_saldo_vuelve_al_area_usuaria(como, cuerpo_base):
    au, jl = como("AU"), como("JL")
    cuerpo = {**cuerpo_base, "items": [_item("Asfalto en frío", 600, "50.00", "bolsa")]}
    rid = _hasta_aprobado(como, cuerpo)  # S/ 30,000.00: verde con saldo de S/ 31,500.00
    _conforme(jl, rid)
    r = jl.put(f"/api/v1/requerimientos/{rid}/cuadro",
               json=_cuadro("35000.00", _cot("35000.00", ruc("2060012345"))))
    assert r.json()["estado_semaforo"] == "ROJO" and r.json()["destino"] == "AREA_USUARIA"
    detalle = au.get(f"/api/v1/requerimientos/{rid}").json()
    assert detalle["estado_actual"] == "Registrado" and detalle["acciones"]["aplicar_ajuste"]
    historial = au.get(f"/api/v1/requerimientos/{rid}/historial").json()["registros"]
    assert historial[-1]["rol"] == "Jefe de Logística y Abastecimientos"
    assert "precio de referencia del mercado" in historial[-1]["observacion"]


def test_cpi55_certificacion_y_orden_cierran_el_tramite(como, cuerpo_base):
    jl, jp = como("JL"), como("JP")
    rid = _hasta_aprobado(como, cuerpo_base)
    _conforme(jl, rid)
    jl.put(f"/api/v1/requerimientos/{rid}/cuadro",
           json=_cuadro("12000.00", _cot("12000.00", ruc("2060012345"))))
    assert any(p["accion"] == "Registrar certificación" and p["requerimiento_id"] == rid
               for p in jp.get("/api/v1/inicio").json()["pendientes"])
    fila = next(f for f in jp.get("/api/v1/expedientes",
                                  params={"estado": "CUADRO_REGISTRADO"}).json()
                if f["requerimiento_id"] == rid)
    assert fila["precio_referencia"] == "12000.00" and fila["plazo_horas"] == 48
    assert jl.get("/api/v1/expedientes", params={"estado": "CUADRO_REGISTRADO"}).status_code \
        == 403
    assert _etapa(jl, rid, "CERTIFICADO").status_code == 403
    assert _etapa(jp, rid, "CERTIFICADO", "Certificación N.° 0123-2026").status_code == 200
    assert any(f["requerimiento_id"] == rid for f in
               jl.get("/api/v1/expedientes", params={"estado": "CERTIFICADO"}).json())
    assert _etapa(jp, rid, "ORDEN_EMITIDA").status_code == 403
    assert _etapa(jl, rid, "ORDEN_EMITIDA", "Orden de compra N.° 045").status_code == 200
    historial = jl.get(f"/api/v1/requerimientos/{rid}/historial").json()
    assert historial["cerrado"] and historial["horas_totales"] is not None
    assert historial["horas_hasta_certificacion"] is not None
    assert historial["etapas_futuras"] == []
    assert _etapa(jl, rid, "ANULADO").status_code == 409  # un trámite cerrado no cambia


def test_cpi56_presupuesto_devuelve_y_logistica_corrige_el_mismo_cuadro(
        como, cuerpo_base, sesion):
    jl, jp = como("JL"), como("JP")
    rid = _hasta_aprobado(como, cuerpo_base)
    _conforme(jl, rid)
    url = f"/api/v1/requerimientos/{rid}/cuadro"
    jl.put(url, json=_cuadro("12000.00", _cot("12000.00", ruc("2060012345"))))
    assert _etapa(jp, rid, "DOCUMENTACION_VALIDADA").status_code == 422  # sin observación
    assert _etapa(jp, rid, "DOCUMENTACION_VALIDADA",
                  "La cotización no tiene fecha de vigencia.").status_code == 200
    cuadro = jl.get(url).json()
    assert cuadro["modo"] == "CORRECCION"
    assert cuadro["devolucion_presupuesto"] == "La cotización no tiene fecha de vigencia."
    fila = next(f for f in jl.get("/api/v1/expedientes",
                                  params={"estado": "DOCUMENTACION_VALIDADA"}).json()
                if f["requerimiento_id"] == rid)
    assert fila["devuelto"] and fila["nota"].startswith("Devuelto por Presupuesto")
    r = jl.put(url, json=_cuadro("11800.00", _cot("11800.00", ruc("2060054321"))))
    assert r.json()["modo"] == "CORRECCION" and r.json()["destino"] == "PRESUPUESTO"
    cuadros = sesion.scalars(select(CuadroComparativo).where(
        CuadroComparativo.id_requerimiento == rid)).all()
    assert len(cuadros) == 1 and str(cuadros[0].precio_referencia) == "11800.00"
    correccion = sesion.scalar(select(Bitacora).where(
        Bitacora.accion == "REGISTRO_CUADRO", Bitacora.recurso_id == rid)
        .order_by(Bitacora.id_bitacora.desc()).limit(1))
    assert correccion.detalle["anterior"]["precio_referencia"] == "12000.00"


def test_cpi57_ambar_con_precio_de_mercado_bloquea_la_certificacion(como, cuerpo_base):
    au, ga, jl, jp = como("AU"), como("GA"), como("JL"), como("JP")
    rid = _registrar(au, _ambar(cuerpo_base))  # meta 0033 sin saldo: ámbar
    jp.post(f"/api/v1/alertas/{rid}/decision", json={"resultado": "CONFIRMADA"})
    _enviar(au, rid)
    _etapa(ga, rid, "APROBADO")
    _conforme(jl, rid)
    r = jl.put(f"/api/v1/requerimientos/{rid}/cuadro",
               json=_cuadro("1000.00", _cot("1000.00", ruc("2060012345"))))
    assert r.json()["estado_semaforo"] == "AMBAR" and r.json()["destino"] == "PRESUPUESTO"
    certificar = _etapa(jp, rid, "CERTIFICADO")
    assert certificar.status_code == 409 and "Panel de alertas" in certificar.json()["detail"]
    assert any(p["accion"] == "Confirmar o denegar" and p["requerimiento_id"] == rid
               for p in jp.get("/api/v1/inicio").json()["pendientes"])
    jp.post(f"/api/v1/alertas/{rid}/decision",
            json={"resultado": "DENEGADA", "sustento": "Sin crédito para el precio de mercado."})
    assert _etapa(jp, rid, "CERTIFICADO").status_code == 409
    assert any(p["accion"] == "Anular por falta de disponibilidad" for p in
               jp.get("/api/v1/inicio").json()["pendientes"] if p["requerimiento_id"] == rid)
    assert _etapa(jp, rid, "ANULADO").status_code == 422  # el motivo es obligatorio
    assert _etapa(jp, rid, "ANULADO", "Sin disponibilidad presupuestal.").status_code == 200
    assert au.get(f"/api/v1/requerimientos/{rid}").json()["estado_actual"] == "Anulado"
