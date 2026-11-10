"""Pruebas unitarias (caja blanca) del semáforo vigente, regla RI-20. CP-U27 a CP-U30."""

import pytest

from app.servicios.validacion.vigencia import SemaforoVigente, semaforo_vigente


@pytest.mark.parametrize("decision", [None, "CONFIRMADA", "DENEGADA"])
def test_cpu27_verde_calculado_es_verde_vigente(decision):
    assert semaforo_vigente("VERDE", decision) == SemaforoVigente.VERDE


def test_cpu28_ambar_confirmado_por_presupuesto_pasa_a_verde():
    assert semaforo_vigente("AMBAR", "CONFIRMADA") == SemaforoVigente.VERDE


def test_cpu29_ambar_sin_decision_o_denegado_no_es_verde():
    assert semaforo_vigente("AMBAR", None) == SemaforoVigente.AMBAR_PENDIENTE
    assert semaforo_vigente("AMBAR", "DENEGADA") == SemaforoVigente.AMBAR_DENEGADO


def test_cpu30_rojo_sigue_rojo():
    assert semaforo_vigente("ROJO", None) == SemaforoVigente.ROJO
