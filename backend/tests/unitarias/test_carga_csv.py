"""Pruebas unitarias de la validación del CSV de respaldo (RF-14, R01, RI-09). CP-U18 a CP-U25."""

import pytest

from app.extraccion.carga_csv import resolver_ruta_segura, validar_csv

CABECERA_MEF = "meta_codigo,meta_nombre,pim,certificacion,compromiso_anual\n"
CABECERA_SEACE = "numero_referencia,descripcion,tipo_objeto,valor_estimado\n"


def test_cpu18_csv_mef_valido():
    resultado = validar_csv("MEF", CABECERA_MEF + "0012,Vías,180000,152000,148500\n")
    assert resultado.es_valido
    assert resultado.filas[0]["codigo"] == "0012"


def test_cpu19_csv_con_marca_bom_de_excel_se_acepta():
    assert validar_csv("MEF", "﻿" + CABECERA_MEF + "0012,Vías,10,5,1\n").es_valido


def test_cpu20_falta_una_columna():
    resultado = validar_csv("MEF", "meta_codigo,pim\n0012,100\n")
    assert not resultado.es_valido
    assert "Faltan las columnas" in resultado.errores[0]


def test_cpu21_monto_negativo_se_rechaza():
    resultado = validar_csv("MEF", CABECERA_MEF + "0012,Vías,-1,0,0\n")
    assert any("negativo" in e for e in resultado.errores)


def test_cpu22_compromiso_mayor_que_certificacion_se_rechaza():
    resultado = validar_csv("MEF", CABECERA_MEF + "0012,Vías,100,50,60\n")
    assert any("compromiso anual <= certificación <= PIM" in e for e in resultado.errores)


def test_cpu23_monto_no_numerico_y_codigo_repetido():
    texto = CABECERA_MEF + "0012,Vías,abc,0,0\n0015,Parques,10,5,1\n0015,Parques,10,5,1\n"
    resultado = validar_csv("MEF", texto)
    assert any("no es un monto numérico" in e for e in resultado.errores)
    assert any("repetido" in e for e in resultado.errores)


def test_cpu24_tipo_de_objeto_del_pac_no_valido():
    resultado = validar_csv("SEACE", CABECERA_SEACE + "PAC-001,Asfalto,MUEBLE,1000\n")
    assert any("tipo de objeto" in e for e in resultado.errores)


def test_cpu25_archivo_sin_filas_se_rechaza():
    resultado = validar_csv("SEACE", CABECERA_SEACE)
    assert not resultado.es_valido
    assert resultado.errores == ["El archivo no contiene filas de datos."]


def test_cpu26_ruta_fuera_de_la_carpeta_de_trabajo_se_rechaza(tmp_path):
    (tmp_path / "saldos.csv").write_text("x", encoding="utf-8")
    assert resolver_ruta_segura("saldos.csv", str(tmp_path)).endswith("saldos.csv")
    with pytest.raises(ValueError, match="carpeta de trabajo"):
        resolver_ruta_segura("../../.env.csv", str(tmp_path))
    with pytest.raises(ValueError, match=".csv"):
        resolver_ruta_segura(".env", str(tmp_path))
