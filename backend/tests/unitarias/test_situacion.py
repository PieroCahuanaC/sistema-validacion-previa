"""Pruebas unitarias del plazo de etapa y de las acciones de la situación (P02, P08, P04)."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.servicios.validacion.situacion import Situacion, horas_a_texto
from app.servicios.validacion.vigencia import SemaforoVigente

AHORA = datetime(2026, 10, 25, 10, 0, tzinfo=ZoneInfo("America/Lima"))


def _situacion(codigo="REGISTRADO", plazo=24, envio=None, vigente=SemaforoVigente.VERDE,
               ajuste=None, desde=AHORA - timedelta(hours=30)):
    return Situacion(
        requerimiento=SimpleNamespace(fecha_envio=envio, id_requerimiento=1),
        estado=SimpleNamespace(codigo=codigo, plazo_horas=plazo, es_final=False),
        validacion=SimpleNamespace(estado_semaforo="VERDE"), decision=None,
        ajuste=SimpleNamespace(opcion=ajuste) if ajuste else None, vigente=vigente,
        desde=desde)


def test_cpu38_en_registrado_el_plazo_de_la_gerencia_corre_desde_el_envio():
    sin_enviar = _situacion()
    assert sin_enviar.horas_en_etapa(AHORA) is None and not sin_enviar.excedido(AHORA)
    enviado_hace_25 = _situacion(envio=AHORA - timedelta(hours=25))
    assert enviado_hace_25.excedido(AHORA)
    enviado_hace_2 = _situacion(envio=AHORA - timedelta(hours=2))
    assert round(enviado_hace_2.horas_en_etapa(AHORA)) == 2
    assert not enviado_hace_2.excedido(AHORA)


def test_cpu39_en_otras_etapas_el_plazo_corre_desde_el_ingreso():
    assert _situacion("APROBADO").excedido(AHORA)  # 30 h frente a 24 h
    assert not _situacion("DOCUMENTACION_VALIDADA", plazo=120).excedido(AHORA)
    assert not _situacion("OBSERVADO", plazo=None).excedido(AHORA)


def test_cpu40_acciones_del_area_usuaria_segun_semaforo_y_ajuste():
    rojo = _situacion(vigente=SemaforoVigente.ROJO)
    assert rojo.puede_aplicar_ajuste and not rojo.puede_anular
    sin_salida = _situacion(vigente=SemaforoVigente.ROJO, ajuste="NINGUNA")
    assert sin_salida.puede_anular and not sin_salida.puede_aplicar_ajuste
    assert _situacion(vigente=SemaforoVigente.AMBAR_DENEGADO).puede_anular
    assert _situacion("OBSERVADO").puede_subsanar
    verde_enviado = _situacion(envio=AHORA)
    assert verde_enviado.en_bandeja_de_gerencia and not verde_enviado.puede_anular
    assert horas_a_texto(30) == "1 d 6 h" and horas_a_texto(5) == "5 h"
    assert horas_a_texto(None) == "—"
