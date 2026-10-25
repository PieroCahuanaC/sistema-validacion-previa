"""Pruebas de las reglas de integridad impuestas por la base de datos. CP-I11 a CP-I14."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.extraccion.carga_csv import cargar_csv
from app.modelos.presupuesto import SaldoMeta


def test_cpi11_validacion_es_de_solo_insercion_ri22(cliente, cuerpo_base, sesion):
    cliente.post("/api/v1/requerimientos", json=cuerpo_base)
    with pytest.raises(DBAPIError, match="RI-22"):
        sesion.execute(text("UPDATE validacion_presupuestal SET estado_semaforo = 'VERDE'"))
    sesion.rollback()


def test_cpi12_monto_distinto_de_la_suma_de_items_falla_al_confirmar_ri14(
    cliente, cuerpo_base, sesion
):
    rid = cliente.post("/api/v1/requerimientos", json=cuerpo_base).json()["requerimiento_id"]
    sesion.execute(text("UPDATE requerimiento SET monto_estimado = 1 WHERE id_requerimiento = :i"),
                   {"i": rid})
    with pytest.raises(DBAPIError, match="RI-14"):
        sesion.commit()
    sesion.rollback()


def test_cpi13_saldo_con_compromiso_mayor_que_certificacion_se_rechaza_ri09(sesion):
    with pytest.raises(DBAPIError):
        sesion.execute(text(
            "INSERT INTO saldo_meta (id_meta, id_carga, pim, certificacion, compromiso_anual) "
            "SELECT id_meta, 1, 100, 50, 60 FROM meta_presupuestal WHERE codigo = '0041'"))
    sesion.rollback()


def test_cpi14_csv_invalido_queda_rechazado_sin_saldos(sesion):
    corte = datetime(2026, 10, 25, tzinfo=ZoneInfo("America/Lima"))
    texto = "meta_codigo,meta_nombre,pim,certificacion,compromiso_anual\n0012,Vías,100,50,60\n"
    carga = cargar_csv(sesion, "MEF", 2026, corte, texto)
    assert carga.resultado == "RECHAZADA"
    assert "compromiso anual" in carga.detalle_error
    assert sesion.scalar(select(SaldoMeta).where(SaldoMeta.id_carga == carga.id_carga)) is None
    assert carga.fecha_corte is None
