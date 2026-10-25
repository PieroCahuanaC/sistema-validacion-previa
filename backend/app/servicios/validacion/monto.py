"""Cálculo y verificación del monto estimado del requerimiento (RF-01, RI-14)."""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.core.errores import DatosNoValidos

CENTIMO = Decimal("0.01")


class ItemConPrecio(Protocol):
    cantidad: Decimal
    precio_unitario_ref: Decimal


def subtotal(item: ItemConPrecio) -> Decimal:
    return (item.cantidad * item.precio_unitario_ref).quantize(CENTIMO, ROUND_HALF_UP)


def calcular_monto_estimado(items: Iterable[ItemConPrecio]) -> Decimal:
    """El monto estimado no se escribe a mano: es la suma de los subtotales de los ítems."""
    lista = list(items)
    if not lista:
        raise DatosNoValidos("El requerimiento debe tener al menos un ítem.")
    return sum((subtotal(i) for i in lista), Decimal("0")).quantize(CENTIMO, ROUND_HALF_UP)


def verificar_tope_8_uit(monto: Decimal, tope: Decimal) -> None:
    """El alcance del sistema son las contrataciones iguales o inferiores a 8 UIT (RI-14)."""
    if monto <= 0:
        raise DatosNoValidos("El monto estimado debe ser mayor que cero.")
    if monto > tope:
        raise DatosNoValidos(
            f"El monto estimado (S/ {monto:,.2f}) supera el tope de 8 UIT (S/ {tope:,.2f})."
        )
