"""Pruebas unitarias del incremento 4A: orden, filtros y tarjetas del tablero (P06) y
parámetros de la regla del semáforo (P14). CP-U45 a CP-U47.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.esquemas.configuracion import ParametrosSemaforo
from app.esquemas.tablero import FilaTablero
from app.servicios.configuracion.reglas import _cambios
from app.servicios.tablero.tablero import FiltrosTablero, _ordenar, _pasa_filtros, _tarjetas
from app.servicios.validacion.vigencia import SemaforoVigente


def _fila(codigo, meta, saldo, necesidad, monto="1000", horas=None, cuello=False,
          cerrado=False, estado="REGISTRADO"):
    return FilaTablero(
        requerimiento_id=int(codigo[-2:]), codigo=codigo, descripcion="x",
        objeto_contratacion="BIEN", unidad_sigla="GDUR", meta_codigo=meta, meta_nombre="Meta",
        monto_estimado=Decimal(monto), saldo_disponible=None if saldo is None else Decimal(saldo),
        fecha_necesidad=necesidad, semaforo_vigente="VERDE", estado_codigo=estado,
        estado_actual=estado.title(), horas_en_etapa=horas, plazo_horas=24,
        cuello_de_botella=cuello, cerrado=cerrado)


def _s(estado="REGISTRADO", vigente=SemaforoVigente.VERDE):
    return SimpleNamespace(codigo_estado=estado, vigente=vigente)


def test_cpu45_orden_del_tablero_por_meta_saldo_y_fecha():
    a = _fila("REQ-01", "0015", "2400", date(2026, 12, 1))
    b = _fila("REQ-02", "0012", "31500", date(2026, 12, 5))
    c = _fila("REQ-03", "0012", "31500", date(2026, 11, 30))
    d = _fila("REQ-04", "0012", None, date(2026, 11, 1))  # sin saldo: al final de su meta
    assert [f.codigo for f in _ordenar([a, b, c, d], "meta", False)] == [
        "REQ-03", "REQ-02", "REQ-04", "REQ-01"]
    e = _fila("REQ-05", "0012", "100", date(2026, 11, 1), monto="5000", horas=3.0)
    f = _fila("REQ-06", "0012", "100", date(2026, 11, 1), monto="9000", horas=None)
    assert [x.codigo for x in _ordenar([e, f], "monto", True)] == ["REQ-06", "REQ-05"]
    # Sin valor («—») va siempre al final, también en orden descendente.
    assert [x.codigo for x in _ordenar([f, e], "tiempo", True)] == ["REQ-05", "REQ-06"]
    assert _ordenar([e], "desconocido", False) == [e]  # orden no previsto: el de la P06


def test_cpu46_filtros_y_tarjetas_del_tablero():
    verde = _fila("REQ-11", "0012", "1", date(2026, 12, 1), cuello=True)
    observado = _fila("REQ-12", "0012", "1", date(2026, 12, 1), estado="OBSERVADO")
    cerrado = _fila("REQ-13", "0015", "1", date(2026, 12, 1), cerrado=True,
                    estado="ORDEN_EMITIDA")
    s_verde, s_obs = _s(), _s("OBSERVADO", SemaforoVigente.VERDE)
    s_cerrado = _s("ORDEN_EMITIDA")
    por_verde = FiltrosTablero(semaforo="VERDE")
    assert _pasa_filtros(verde, s_verde, por_verde)
    assert not _pasa_filtros(observado, s_obs, por_verde)  # el observado no cuenta por color
    assert _pasa_filtros(observado, s_obs, FiltrosTablero(estado="OBSERVADO"))
    assert not _pasa_filtros(cerrado, s_cerrado, FiltrosTablero(meta="0012"))
    assert _pasa_filtros(verde, s_verde, FiltrosTablero(buscar=" req-11 "))
    assert not _pasa_filtros(observado, s_obs, FiltrosTablero(cuello_de_botella=True))
    rojo = _s(vigente=SemaforoVigente.ROJO)
    ambar = _s(vigente=SemaforoVigente.AMBAR_PENDIENTE)
    t = _tarjetas([(verde, s_verde), (observado, s_obs), (cerrado, s_cerrado),
                   (_fila("REQ-14", "0012", "1", date(2026, 12, 1)), rojo),
                   (_fila("REQ-15", "0012", "1", date(2026, 12, 1)), ambar)])
    assert (t.en_tramite, t.verde, t.ambar, t.rojo, t.observado, t.cuello_de_botella,
            t.cerrados) == (4, 1, 1, 1, 1, 1, 1)


BASE = {"umbral_disponibilidad_pct": 100, "columna_comparacion": "COMPROMISO",
        "tratamiento_no_previsto_pac": "AMBAR", "antiguedad_maxima_dias": 7, "valor_uit": 5500.0}


@pytest.mark.parametrize("cambio", [
    {"umbral_disponibilidad_pct": 99}, {"umbral_disponibilidad_pct": 201},
    {"antiguedad_maxima_dias": 0}, {"antiguedad_maxima_dias": 32}, {"valor_uit": 0},
    {"valor_uit": "5500.555"}, {"columna_comparacion": "PIM"},
    {"tratamiento_no_previsto_pac": "ROJO"}, {"otro_parametro": 1},
])
def test_cpu47_rangos_de_la_regla_y_cambios_entre_versiones(cambio):
    with pytest.raises(ValidationError):
        ParametrosSemaforo.model_validate({**BASE, **cambio})
    p = ParametrosSemaforo.model_validate({**BASE, "valor_uit": "5350.00"})
    assert p.a_json()["valor_uit"] == 5350.0
    # 5500.0 de la semilla y "5500.00" de la pantalla son el mismo valor: no es un cambio.
    assert _cambios(BASE, {**BASE, "valor_uit": "5500.00"}) == []
    cambios = _cambios(BASE, {**BASE, "valor_uit": 5350.0, "antiguedad_maxima_dias": 5})
    assert [(c.parametro, c.anterior, c.nuevo) for c in cambios] == [
        ("antiguedad_maxima_dias", "7", "5"), ("valor_uit", "5500.00", "5350.00")]
