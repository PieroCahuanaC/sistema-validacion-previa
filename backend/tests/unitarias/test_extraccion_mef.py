"""Pruebas unitarias de la extracción automática del MEF (RF-14, R01). CP-U49 a CP-U51."""

import io
import zipfile
from datetime import UTC, datetime

import pytest

from app.extraccion import mef
from app.extraccion.carga_csv import validar_csv
from app.extraccion.mef import ErrorExtraccion, a_csv, fecha_corte, saldos_por_meta

CABECERA = ("ANO_EJE,MES_EJE,SEC_EJEC,SEC_FUNC,META_NOMBRE,MONTO_PIA,MONTO_PIM,"
            "MONTO_CERTIFICADO,MONTO_COMPROMETIDO_ANUAL,MONTO_DEVENGADO")


def zip_mef(*filas: str, cabecera: str = CABECERA) -> io.BytesIO:
    contenido = "\n".join([cabecera, *filas]) + "\n"
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("2026-Gasto-Diario.csv", contenido)
    salida.seek(0)
    return salida


def test_cpu49_suma_por_meta_solo_de_la_ejecutora():
    archivo = zip_mef(
        # Los montos anuales vienen en la fila del mes 0; las demás filas traen la ejecución.
        '"2026","0","300354","12","VIAS VECINALES","100000","180000","0","0","0"',
        '"2026","3","300354","12","VIAS VECINALES","0","0","152000.50","148500.25","9000"',
        '"2026","0","300354","7","PARQUES","0","5000","4000","3000","0"',
        '"2026","0","300354","9","META SIN PIM","0","0","0","0","0"',
        # Otra ejecutora que lleva «300354» en otra columna: no se suma.
        '"2026","0","300999","12","OTRA","0","999999","0","0","300354"',
        '"2026","0","1300354","12","OTRA","0","888888","0","0","0"',
    )
    metas = saldos_por_meta(archivo)
    assert [(m.codigo, str(m.pim), str(m.certificacion), str(m.compromiso_anual)) for m in metas] \
        == [("0007", "5000", "4000", "3000"), ("0012", "180000", "152000.50", "148500.25")]
    resultado = validar_csv("MEF", a_csv(metas))  # misma validación que la carga CSV
    assert resultado.es_valido and resultado.filas[1]["nombre"] == "VIAS VECINALES"


@pytest.mark.parametrize(("archivo", "mensaje"), [
    (zip_mef('"2026","0","300354","1","X","0","1","0","0"',
             cabecera="ANO_EJE,MES_EJE,SEC_EJEC,SEC_FUNC,META_NOMBRE,MONTO_PIA,MONTO_PIM,"
                      "MONTO_CERTIFICADO"), "faltan las columnas: MONTO_COMPROMETIDO_ANUAL"),
    (zip_mef('"2026","0","400100","1","X","0","1","0","0","0"'), "no tiene registros"),
    (zip_mef('"2026","0","300354","1","X","0","abc","0","0","0"'), "no numérico"),
    (io.BytesIO(b"<html>Mantenimiento</html>"), "no es un ZIP"),
])
def test_cpu50_formato_inesperado_detiene_la_extraccion(archivo, mensaje):
    with pytest.raises(ErrorExtraccion, match=mensaje):
        saldos_por_meta(archivo)


def test_cpu51_fecha_de_corte_y_reintentos():
    # Publicado el 17/11 a las 08:48 de Lima: trae lo registrado hasta el 16/11.
    assert fecha_corte(datetime(2026, 11, 17, 13, 48, tzinfo=UTC)).isoformat() \
        == "2026-11-16T00:00:00-05:00"
    # A las 22:00 de Lima del 17/11 (03:00 UTC del 18/11) sigue siendo el corte del 16/11.
    assert fecha_corte(datetime(2026, 11, 18, 3, 0, tzinfo=UTC)).day == 16

    intentos = []

    def falla_dos_veces():
        intentos.append(1)
        if len(intentos) < 3:
            raise ConnectionError("tiempo agotado")
        return "ok"

    assert mef._con_reintentos(falla_dos_veces, "Descarga", espera=0) == "ok"
    def siempre_falla():
        raise ConnectionError("tiempo agotado")

    with pytest.raises(ErrorExtraccion, match="Descarga: tiempo agotado"):
        mef._con_reintentos(siempre_falla, "Descarga", espera=0)
    assert mef.main(["--archivo", "/etc/passwd", "--corte", "2026-11-16"]) == 2  # CWE-22
