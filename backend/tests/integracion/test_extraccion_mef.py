"""Pruebas de integración de la extracción automática del MEF (RF-14, R01).
CP-I65 a CP-I67 y CP-I70.

Usan el año fiscal 2024 para no tocar la base de 2026 con la que trabajan las demás pruebas, y
una fuente simulada en lugar del portal del MEF (la descarga real se prueba a mano, ver
docs/extraccion-mef.md).
"""

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.extraccion.mef import ErrorExtraccion, ejecutar
from app.modelos.presupuesto import CargaDatos, MetaPresupuestal, SaldoMeta
from app.modelos.seguridad import Bitacora
from app.repositorios.presupuesto import RepositorioPresupuesto
from tests.integracion.conftest import AHORA_FIJO
from tests.unitarias.test_extraccion_mef import zip_mef

ANIO = 2024
FILAS = ('"2024","0","300354","12","VIAS VECINALES","0","180000","152000","148500","0"',
         '"2024","0","300354","15","PARQUES Y JARDINES","0","60000","58200","57600","0"')


class FuenteFalsa:
    def __init__(self, publicado: datetime, *filas: str, error: str | None = None,
                 cabecera: str | None = None) -> None:
        self.publicado, self.filas, self.error, self.cabecera = publicado, filas, error, cabecera
        self.descargas = 0

    def ultima_modificacion(self, url: str) -> datetime:
        assert url.endswith(f"/{ANIO}-Gasto-Diario.zip")
        return self.publicado

    def descargar(self, url: str, destino: Path) -> None:
        self.descargas += 1
        if self.error:
            raise ErrorExtraccion(self.error)
        extra = {"cabecera": self.cabecera} if self.cabecera else {}
        destino.write_bytes(zip_mef(*self.filas, **extra).getvalue())


def _vigente(sesion):
    sesion.expire_all()
    return RepositorioPresupuesto(sesion).ultima_carga_exitosa("MEF", ANIO)


def _con_carga_vigente(sesion):
    """Garantiza una carga buena vigente, para que el caso no dependa de que CP-I65 corra antes."""
    vigente = _vigente(sesion)
    if vigente is None:
        r = ejecutar(sesion, ANIO, AHORA_FIJO,
                     FuenteFalsa(datetime(2024, 12, 20, 13, 0, tzinfo=UTC), *FILAS))
        assert r.resultado == "EXITOSA", r.mensaje
        vigente = _vigente(sesion)
    return vigente


def test_cpi65_extraccion_exitosa_y_sin_cambios_al_repetir(sesion):
    fuente = FuenteFalsa(datetime(2024, 12, 20, 13, 0, tzinfo=UTC), *FILAS)
    r = ejecutar(sesion, ANIO, AHORA_FIJO, fuente)
    assert (r.resultado, r.metas) == ("EXITOSA", 2), r.mensaje
    carga = sesion.get(CargaDatos, r.id_carga)
    assert carga.origen == "AUTOMATICA" and carga.fecha_corte.date() == date(2024, 12, 19)
    assert _vigente(sesion).id_carga == r.id_carga
    saldos = sesion.scalars(select(SaldoMeta).where(SaldoMeta.id_carga == r.id_carga)).all()
    assert sorted(str(s.pim) for s in saldos) == ["180000.00", "60000.00"]
    registro = sesion.scalar(select(Bitacora).order_by(Bitacora.id_bitacora.desc()).limit(1))
    assert (registro.actor_servicio, registro.accion, registro.resultado) == (
        "EXTRACCION_MEF", "EXTRACCION_DATOS", "EXITO")
    assert registro.id_usuario is None and registro.detalle["filas"] == 2

    cargas = sesion.scalar(select(func.count()).select_from(CargaDatos))
    otra_vez = ejecutar(sesion, ANIO, AHORA_FIJO, fuente)  # misma publicación del MEF
    assert otra_vez.resultado == "SIN_CAMBIOS" and fuente.descargas == 1  # ni siquiera descarga
    assert sesion.scalar(select(func.count()).select_from(CargaDatos)) == cargas


def test_cpi66_falla_de_la_fuente_conserva_la_ultima_carga_buena(sesion):
    vigente = _con_carga_vigente(sesion)
    caida = FuenteFalsa(datetime(2024, 12, 21, 13, 0, tzinfo=UTC),
                        error="No se pudo descargar el archivo del MEF: tiempo agotado")
    r = ejecutar(sesion, ANIO, AHORA_FIJO, caida)
    assert r.resultado == "FALLIDA"
    fallida = sesion.get(CargaDatos, r.id_carga)
    assert fallida.fecha_corte is None and "tiempo agotado" in fallida.detalle_error
    assert _vigente(sesion).id_carga == vigente.id_carga  # el semáforo sigue con la anterior
    registro = sesion.scalar(select(Bitacora).order_by(Bitacora.id_bitacora.desc()).limit(1))
    assert registro.resultado == "ERROR" and registro.detalle["resultado"] == "FALLIDA"

    otro_formato = FuenteFalsa(datetime(2024, 12, 21, 13, 0, tzinfo=UTC), FILAS[0],
                               cabecera="ANO_EJE,SEC_EJEC,META,PIM")
    r = ejecutar(sesion, ANIO, AHORA_FIJO, otro_formato)
    assert r.resultado == "FALLIDA" and "Cambió el formato" in r.mensaje
    assert _vigente(sesion).id_carga == vigente.id_carga


def test_cpi67_datos_incoherentes_se_rechazan_y_carga_desde_archivo(sesion, tmp_path):
    vigente = _con_carga_vigente(sesion)
    incoherente = FuenteFalsa(datetime(2024, 12, 22, 13, 0, tzinfo=UTC),
                              '"2024","0","300354","12","VIAS","0","1000","2000","100","0"')
    r = ejecutar(sesion, ANIO, AHORA_FIJO, incoherente)  # certificación mayor que el PIM
    assert r.resultado == "RECHAZADA" and "Fila 2" in r.mensaje
    assert sesion.scalar(select(func.count()).select_from(SaldoMeta)
                         .where(SaldoMeta.id_carga == r.id_carga)) == 0
    assert _vigente(sesion).id_carga == vigente.id_carga

    # Contingencia: un ZIP ya descargado, con una fecha de corte posterior; la meta 0015 ya no
    # figura y deja de ofrecerse al registrar.
    archivo = tmp_path / "2024-Gasto-Diario.zip"
    archivo.write_bytes(zip_mef(FILAS[0]).getvalue())
    r = ejecutar(sesion, ANIO, AHORA_FIJO, archivo=archivo, corte=date(2024, 12, 30))
    assert r.resultado == "EXITOSA" and _vigente(sesion).id_carga == r.id_carga
    activas = sesion.scalars(select(MetaPresupuestal.codigo).where(
        MetaPresupuestal.anio_fiscal == ANIO, MetaPresupuestal.activa.is_(True))).all()
    assert activas == ["0012"]
    assert ejecutar(sesion, ANIO, AHORA_FIJO, archivo=archivo).resultado == "FALLIDA"  # sin corte


def test_cpi70_linea_de_comandos_con_archivo_zip_y_csv(sesion, tmp_path, monkeypatch, capsys):
    """Defecto DEF-06: la contingencia por línea de comandos con el ZIP del MEF se rechazaba
    por la extensión. Usa 2024, como las demás pruebas de este archivo, con un corte posterior."""
    from app.extraccion import carga_csv, mef

    monkeypatch.chdir(tmp_path)
    (tmp_path / "2024-Gasto-Diario.zip").write_bytes(zip_mef(FILAS[0]).getvalue())
    assert mef.main(["--anio", "2024", "--archivo", "2024-Gasto-Diario.zip",
                     "--corte", "2024-12-31"]) == 0
    assert "Extracción MEF 2024: EXITOSA" in capsys.readouterr().out

    (tmp_path / "pac.csv").write_text(
        "numero_referencia,descripcion,tipo_objeto,valor_estimado\nPAC-9,Asfalto,BIEN,1000\n",
        encoding="utf-8")
    assert carga_csv.main(["SEACE", "2024", "2024-12-31", "pac.csv"]) == 0
    assert "EXITOSA" in capsys.readouterr().out
    sesion.expire_all()
    assert RepositorioPresupuesto(sesion).ultima_carga_exitosa("SEACE", 2024) is not None
