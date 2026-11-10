"""Semáforo vigente de un requerimiento (regla RI-20 de la Práctica 6).

El semáforo calculado por el sistema (CU-01) puede quedar corregido por la decisión del Jefe
de Presupuesto sobre un ámbar (CU-06). El vigente es verde si la última validación es verde
o es ámbar con decisión CONFIRMADA; a la Gerencia de Administración solo llegan verdes
(observación del asesor a la Práctica 7). Es una función pura, sin acceso a la base de datos.
"""

from enum import StrEnum


class SemaforoVigente(StrEnum):
    VERDE = "VERDE"
    AMBAR_PENDIENTE = "AMBAR_PENDIENTE"  # ámbar sin decisión de Presupuesto
    AMBAR_DENEGADO = "AMBAR_DENEGADO"  # Presupuesto denegó: solo queda anular
    ROJO = "ROJO"


def semaforo_vigente(estado_validacion: str, resultado_decision: str | None) -> SemaforoVigente:
    """Combina la última validación con la decisión de Presupuesto, si la hay."""
    if estado_validacion == "VERDE":
        return SemaforoVigente.VERDE
    if estado_validacion == "ROJO":
        return SemaforoVigente.ROJO
    if resultado_decision == "CONFIRMADA":
        return SemaforoVigente.VERDE
    if resultado_decision == "DENEGADA":
        return SemaforoVigente.AMBAR_DENEGADO
    return SemaforoVigente.AMBAR_PENDIENTE
