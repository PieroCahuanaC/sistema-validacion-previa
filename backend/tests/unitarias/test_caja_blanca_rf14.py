"""Pruebas de caja blanca de la base presupuestal (RF-14), diseñadas sobre las ramas que la
medición de cobertura de la Práctica 9 dejó sin ejecutar. CP-U55 a CP-U58.
"""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from app.extraccion import carga_csv, mef
from app.extraccion.carga_csv import resolver_ruta_segura, validar_csv
from app.extraccion.mef import ErrorExtraccion, FuenteHttp

CABECERA_MEF = "meta_codigo,meta_nombre,pim,certificacion,compromiso_anual\n"
CABECERA_SEACE = "numero_referencia,descripcion,tipo_objeto,valor_estimado\n"


@pytest.mark.parametrize(("fuente", "fila", "mensaje"), [
    ("MEF", ",Vías,100,90,80", "el código y el nombre de la meta son obligatorios"),
    ("MEF", "0012, ,100,90,80", "el código y el nombre de la meta son obligatorios"),
    ("SEACE", " ,Asfalto,BIEN,1000", "la referencia y la descripción son obligatorias"),
    ("SEACE", "PAC-1,Asfalto,BIEN,mil", "valor_estimado"),
])
def test_cpu55_ramas_de_validacion_de_filas_vacias_o_invalidas(fuente, fila, mensaje):
    cabecera = CABECERA_MEF if fuente == "MEF" else CABECERA_SEACE
    resultado = validar_csv(fuente, cabecera + fila + "\n")
    assert not resultado.es_valido
    assert any(mensaje in e for e in resultado.errores)


def test_cpu56_ruta_segura_segun_extension_y_cli_sin_base(tmp_path, monkeypatch, capsys):
    zip_ = tmp_path / "2026-Gasto-Diario.zip"
    zip_.write_bytes(b"")
    # Defecto DEF-06: antes la ruta del ZIP del MEF se rechazaba por no ser .csv.
    assert resolver_ruta_segura(str(zip_), str(tmp_path), ".zip") == str(zip_)
    with pytest.raises(ValueError, match="extensión .csv"):
        resolver_ruta_segura(str(zip_), str(tmp_path))
    # La línea de comandos valida los argumentos antes de abrir la base de datos.
    monkeypatch.chdir(tmp_path)
    assert carga_csv.main(["MEF", "2026"]) == 2
    assert carga_csv.main(["OTRA", "2026", "2026-11-16", "a.csv"]) == 2
    assert carga_csv.main(["MEF", "2026", "2026-11-16", "../fuera.csv"]) == 2
    assert "fuera de la carpeta de trabajo" in capsys.readouterr().out


class _Respuesta:
    def __init__(self, cabeceras=None, bloques=(), error=None):
        self.headers = cabeceras or {}
        self._bloques = bloques
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def iter_content(self, chunk_size):
        assert chunk_size == 1 << 20  # descarga por bloques de 1 MB, sin cargar todo en memoria
        yield from self._bloques


class _HttpFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def head(self, url, timeout, allow_redirects):
        self.llamadas.append(("HEAD", url, timeout))
        return self._siguiente()

    @contextmanager
    def get(self, url, stream, timeout):
        self.llamadas.append(("GET", url, timeout))
        yield self._siguiente()

    def _siguiente(self):
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_cpu57_fuente_http_consulta_la_fecha_con_reintentos():
    fuente = FuenteHttp(espera=0)
    assert "SistemaValidacionPrevia" in fuente._http.headers["User-Agent"]
    fuente._http = _HttpFalso([
        ConnectionError("tiempo agotado"),
        _Respuesta({"Last-Modified": "Tue, 17 Nov 2026 13:48:00 GMT"}),
    ])
    assert fuente.ultima_modificacion(mef.URL_ARCHIVO.format(anio=2026)) == datetime(
        2026, 11, 17, 13, 48, tzinfo=UTC)
    assert [m for m, *_ in fuente._http.llamadas] == ["HEAD", "HEAD"]  # un reintento
    assert fuente._http.llamadas[0][2] == (30, 60)  # siempre con tiempo máximo


def test_cpu58_fuente_http_descarga_por_bloques_y_falla_tras_tres_intentos(tmp_path):
    destino = tmp_path / "mef.zip"
    fuente = FuenteHttp(espera=0)
    fuente._http = _HttpFalso([_Respuesta(bloques=[b"PK", b"\x03\x04"])])
    fuente.descargar("https://ejemplo/mef.zip", destino)
    assert destino.read_bytes() == b"PK\x03\x04"

    fuente._http = _HttpFalso([_Respuesta(error=OSError("HTTP 503"))] * 3)
    with pytest.raises(ErrorExtraccion, match="No se pudo descargar el archivo del MEF"):
        fuente.descargar("https://ejemplo/mef.zip", destino)
    assert len(fuente._http.llamadas) == 3  # REINTENTOS
