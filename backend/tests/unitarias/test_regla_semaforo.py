"""Pruebas unitarias de la regla del semáforo (RF-02, RF-03; CU-01). Casos CP-U01 a CP-U12."""

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.servicios.validacion.regla_semaforo import (
    EntradaSemaforo,
    Motivo,
    ParametrosRegla,
    SaldoVigente,
    Semaforo,
    evaluar_semaforo,
    opciones_de_ajuste,
)

AHORA = datetime(2026, 10, 25, 10, 0, tzinfo=ZoneInfo("America/Lima"))
PARAMETROS = ParametrosRegla.desde_json({
    "umbral_disponibilidad_pct": 100, "columna_comparacion": "COMPROMISO",
    "tratamiento_no_previsto_pac": "AMBAR", "antiguedad_maxima_dias": 7, "valor_uit": 5500,
})
# Meta 0012 de los datos mock: PIM 180 000, certificación 152 000, compromiso 148 500.
SALDO = SaldoVigente(Decimal("180000"), Decimal("152000"), Decimal("148500"),
                     AHORA - timedelta(days=1))  # disponible = 31 500


def entrada(monto: str, saldo=SALDO, previsto=True, parametros=PARAMETROS) -> EntradaSemaforo:
    return EntradaSemaforo(Decimal(monto), saldo, previsto, parametros, AHORA)


def test_cpu01_saldo_suficiente_devuelve_verde_disponible():
    resultado = evaluar_semaforo(entrada("12750.00"))
    assert (resultado.estado, resultado.motivo) == (Semaforo.VERDE, Motivo.DISPONIBLE)
    assert resultado.saldo_disponible == Decimal("31500")


def test_cpu02_saldo_insuficiente_devuelve_rojo():
    resultado = evaluar_semaforo(entrada("37800.00"))
    assert (resultado.estado, resultado.motivo) == (Semaforo.ROJO,
                                                    Motivo.PRESUPUESTO_INSUFICIENTE)


def test_cpu03_monto_igual_al_disponible_es_verde():
    assert evaluar_semaforo(entrada("31500.00")).estado is Semaforo.VERDE


def test_cpu04_meta_sin_saldo_devuelve_ambar_sin_datos():
    resultado = evaluar_semaforo(entrada("1000.00", saldo=None))
    assert (resultado.estado, resultado.motivo) == (Semaforo.AMBAR, Motivo.SIN_DATOS_META)
    assert resultado.saldo_disponible is None


def test_cpu05_dato_mas_antiguo_que_el_maximo_devuelve_ambar_desactualizado():
    antiguo = replace(SALDO, fecha_corte=AHORA - timedelta(days=8))
    resultado = evaluar_semaforo(entrada("1000.00", saldo=antiguo))
    assert (resultado.estado, resultado.motivo) == (Semaforo.AMBAR, Motivo.DATO_DESACTUALIZADO)


def test_cpu06_dato_desactualizado_tiene_prioridad_sobre_insuficiencia():
    antiguo = replace(SALDO, fecha_corte=AHORA - timedelta(days=30))
    assert evaluar_semaforo(entrada("99999.00", saldo=antiguo)).motivo is (
        Motivo.DATO_DESACTUALIZADO)


def test_cpu07_no_previsto_en_pac_devuelve_ambar_por_defecto():
    resultado = evaluar_semaforo(entrada("1000.00", previsto=False))
    assert (resultado.estado, resultado.motivo) == (Semaforo.AMBAR, Motivo.NO_PREVISTO_PAC)


def test_cpu08_no_previsto_en_pac_con_tratamiento_verde():
    parametros = replace(PARAMETROS, tratamiento_no_previsto_pac=Semaforo.VERDE)
    resultado = evaluar_semaforo(entrada("1000.00", previsto=False, parametros=parametros))
    assert (resultado.estado, resultado.motivo) == (Semaforo.VERDE, Motivo.NO_PREVISTO_PAC)


def test_cpu09_insuficiencia_tiene_prioridad_sobre_falta_de_pac():
    assert evaluar_semaforo(entrada("40000.00", previsto=False)).estado is Semaforo.ROJO


def test_cpu10_umbral_de_110_por_ciento_vuelve_rojo_un_caso_limite():
    parametros = replace(PARAMETROS, umbral_disponibilidad_pct=Decimal("110"))
    # 30 000 x 1,10 = 33 000 > 31 500 disponible
    assert evaluar_semaforo(entrada("30000.00", parametros=parametros)).estado is Semaforo.ROJO


def test_cpu11_columna_certificacion_cambia_el_saldo_disponible():
    parametros = replace(PARAMETROS, columna_comparacion="CERTIFICACION")
    resultado = evaluar_semaforo(entrada("30000.00", parametros=parametros))
    assert resultado.saldo_disponible == Decimal("28000")  # 180 000 - 152 000
    assert resultado.estado is Semaforo.ROJO


@pytest.mark.parametrize(("monto", "esperado"), [
    ("37800.00", ["REFORMULAR", "REPROGRAMAR"]),
    ("1000.00", []),
])
def test_cpu12_opciones_de_ajuste_solo_ante_rojo_y_sin_fraccionar(monto, esperado):
    assert opciones_de_ajuste(evaluar_semaforo(entrada(monto))) == esperado
