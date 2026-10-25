"""Pruebas unitarias del monto estimado y del tope de 8 UIT (RF-01, RI-14). CP-U13 a CP-U17."""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.core.errores import DatosNoValidos
from app.servicios.validacion.monto import calcular_monto_estimado, verificar_tope_8_uit

TOPE = Decimal("44000.00")  # 8 x UIT 2026 de S/ 5 500


@dataclass
class Item:
    cantidad: Decimal
    precio_unitario_ref: Decimal


def test_cpu13_monto_es_la_suma_de_los_subtotales():
    items = [Item(Decimal("800"), Decimal("42.50")), Item(Decimal("40"), Decimal("95.00"))]
    assert calcular_monto_estimado(items) == Decimal("37800.00")


def test_cpu14_subtotal_se_redondea_a_centimos():
    assert calcular_monto_estimado([Item(Decimal("3"), Decimal("0.335"))]) == Decimal("1.01")


def test_cpu15_requerimiento_sin_items_se_rechaza():
    with pytest.raises(DatosNoValidos, match="al menos un ítem"):
        calcular_monto_estimado([])


def test_cpu16_monto_igual_a_8_uit_se_acepta():
    verificar_tope_8_uit(Decimal("44000.00"), TOPE)


@pytest.mark.parametrize("monto", ["44000.01", "0"])
def test_cpu17_monto_fuera_del_rango_se_rechaza(monto):
    with pytest.raises(DatosNoValidos):
        verificar_tope_8_uit(Decimal(monto), TOPE)
