"""Regla del semáforo presupuestal (RF-02, RF-03; CU-01).

Es una función pura: no accede a la base de datos ni al reloj del sistema. Recibe el monto,
el saldo vigente de la meta, si el requerimiento está previsto en el PAC y los parámetros de
la versión vigente de la regla, y devuelve el color y el motivo.

Se implementa como una cadena de reglas (patrón Chain of Responsibility, sección 1.7 de la
Práctica 5): cada eslabón decide o deja pasar al siguiente, en el orden de los flujos
alternativos del CU-01 (Tabla 13 de la Práctica 6):
  1. ausencia del dato (SIN_DATOS_META) y 2. antigüedad del dato (DATO_DESACTUALIZADO),
  3. insuficiencia presupuestal (PRESUPUESTO_INSUFICIENTE),
  4. falta de previsión en el PAC (NO_PREVISTO_PAC), y si nada lo detiene, 5. DISPONIBLE.
Agregar un motivo nuevo es agregar un eslabón, sin modificar los existentes (principio O).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class Semaforo(StrEnum):
    VERDE = "VERDE"
    AMBAR = "AMBAR"
    ROJO = "ROJO"


class Motivo(StrEnum):
    DISPONIBLE = "DISPONIBLE"
    PRESUPUESTO_INSUFICIENTE = "PRESUPUESTO_INSUFICIENTE"
    SIN_DATOS_META = "SIN_DATOS_META"
    DATO_DESACTUALIZADO = "DATO_DESACTUALIZADO"
    NO_PREVISTO_PAC = "NO_PREVISTO_PAC"


@dataclass(frozen=True)
class ParametrosRegla:
    """Contenido de regla_semaforo.parametros (Tabla 11 de la Práctica 6)."""

    umbral_disponibilidad_pct: Decimal
    columna_comparacion: str  # COMPROMISO o CERTIFICACION
    tratamiento_no_previsto_pac: Semaforo  # AMBAR o VERDE
    antiguedad_maxima_dias: int
    valor_uit: Decimal

    @classmethod
    def desde_json(cls, datos: dict) -> "ParametrosRegla":
        return cls(
            umbral_disponibilidad_pct=Decimal(str(datos["umbral_disponibilidad_pct"])),
            columna_comparacion=datos["columna_comparacion"],
            tratamiento_no_previsto_pac=Semaforo(datos["tratamiento_no_previsto_pac"]),
            antiguedad_maxima_dias=int(datos["antiguedad_maxima_dias"]),
            valor_uit=Decimal(str(datos["valor_uit"])).quantize(Decimal("0.01")),
        )

    @property
    def tope_8_uit(self) -> Decimal:
        return self.valor_uit * 8


@dataclass(frozen=True)
class SaldoVigente:
    """Saldo de la meta en la última carga exitosa del MEF (RI-17)."""

    pim: Decimal
    certificacion: Decimal
    compromiso_anual: Decimal
    fecha_corte: datetime


@dataclass(frozen=True)
class EntradaSemaforo:
    monto: Decimal
    saldo: SaldoVigente | None
    previsto_en_pac: bool
    parametros: ParametrosRegla
    momento: datetime


@dataclass(frozen=True)
class ResultadoSemaforo:
    estado: Semaforo
    motivo: Motivo
    saldo_disponible: Decimal | None


def calcular_saldo_disponible(saldo: SaldoVigente, parametros: ParametrosRegla) -> Decimal:
    """Saldo presupuestal disponible: PIM menos la columna configurada (RF-02).

    Es crédito presupuestario aún no comprometido, no dinero en caja (observación del asesor).
    """
    if parametros.columna_comparacion == "CERTIFICACION":
        return saldo.pim - saldo.certificacion
    return saldo.pim - saldo.compromiso_anual


# Cada eslabón recibe el saldo ya verificado como no nulo y el disponible calculado una vez.
Eslabon = Callable[[EntradaSemaforo, SaldoVigente, Decimal], ResultadoSemaforo | None]


def _dato_desactualizado(
    entrada: EntradaSemaforo, saldo: SaldoVigente, disponible: Decimal
) -> ResultadoSemaforo | None:
    antiguedad = entrada.momento - saldo.fecha_corte
    if antiguedad > timedelta(days=entrada.parametros.antiguedad_maxima_dias):
        return ResultadoSemaforo(Semaforo.AMBAR, Motivo.DATO_DESACTUALIZADO, disponible)
    return None


def _presupuesto_insuficiente(
    entrada: EntradaSemaforo, _saldo: SaldoVigente, disponible: Decimal
) -> ResultadoSemaforo | None:
    # Verde exige que el disponible cubra el monto multiplicado por el umbral (100 % a 200 %).
    exigido = entrada.monto * entrada.parametros.umbral_disponibilidad_pct / 100
    if disponible < exigido:
        return ResultadoSemaforo(Semaforo.ROJO, Motivo.PRESUPUESTO_INSUFICIENTE, disponible)
    return None


def _no_previsto_pac(
    entrada: EntradaSemaforo, _saldo: SaldoVigente, disponible: Decimal
) -> ResultadoSemaforo | None:
    if not entrada.previsto_en_pac:
        estado = entrada.parametros.tratamiento_no_previsto_pac
        return ResultadoSemaforo(estado, Motivo.NO_PREVISTO_PAC, disponible)
    return None


CADENA: tuple[Eslabon, ...] = (
    _dato_desactualizado,
    _presupuesto_insuficiente,
    _no_previsto_pac,
)


def evaluar_semaforo(entrada: EntradaSemaforo) -> ResultadoSemaforo:
    """Clasifica el requerimiento en verde, ámbar o rojo (RF-03)."""
    # Primer eslabón: sin saldo no hay nada que comparar (CU-01, flujo 2a). Resolverlo aquí
    # permite que el resto de la cadena reciba un saldo garantizado, sin aserciones.
    if entrada.saldo is None:
        return ResultadoSemaforo(Semaforo.AMBAR, Motivo.SIN_DATOS_META, None)
    disponible = calcular_saldo_disponible(entrada.saldo, entrada.parametros)
    for eslabon in CADENA:
        resultado = eslabon(entrada, entrada.saldo, disponible)
        if resultado is not None:
            return resultado
    return ResultadoSemaforo(Semaforo.VERDE, Motivo.DISPONIBLE, disponible)


def opciones_de_ajuste(resultado: ResultadoSemaforo) -> list[str]:
    """Opciones del RF-04 que se ofrecen al Área Usuaria: solo ante un semáforo rojo.

    La opción Fraccionar se retiró por el artículo 50 de la Ley N.° 32069 (Práctica 7).
    """
    if resultado.estado is Semaforo.ROJO:
        return ["REFORMULAR", "REPROGRAMAR"]
    return []
