"""Extracción automática de la base presupuestal del MEF (RF-14; riesgo R01).

Fuente: conjunto «Presupuesto y Ejecución de Gasto» del Portal de Datos Abiertos del MEF,
archivo diario {año}-Gasto-Diario.zip, que el MEF declara proveniente de la Consulta Amigable y
publica todos los días. Se usa este archivo y no la página de la Consulta Amigable porque el
navegador de la Consulta Amigable no baja hasta la meta (secuencia funcional): su nivel más
fino es la actividad, y está detrás de una protección contra robots que puede bloquear el
script. El archivo abierto sí trae la meta (SEC_FUNC y META_NOMBRE) con su PIM, certificación y
compromiso anual, y sus totales coinciden con los de la Consulta Amigable para la ejecutora.

El proceso: (1) consulta la fecha de publicación del archivo; si ya se cargó esa publicación,
termina sin cambios; (2) descarga el ZIP (unos 600 MB), lo recorre sin descomprimirlo en disco
y suma, por meta, las filas de la ejecutora 300354 (Municipalidad Distrital de Uchumayo); (3)
pasa el resultado por la misma validación que la carga CSV de respaldo (RI-09, RI-11) y lo
registra con origen AUTOMATICA. Si algo falla, registra la carga como FALLIDA y el semáforo
sigue usando la última carga exitosa (plan de respuesta del R01).

Uso (GitHub Actions o manual):
    python -m app.extraccion.mef                    # año en curso, desde el MEF
    python -m app.extraccion.mef --anio 2026 --archivo 2026-Gasto-Diario.zip --corte 2026-11-16
"""

import argparse
import csv
import io
import os
import sys
import tempfile
import time
import uuid
import zipfile
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import BinaryIO, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extraccion.carga_csv import COLUMNAS, cargar_csv, resolver_ruta_segura

# Fuera de la API hay que registrar todos los modelos: la bitácora referencia a rol y usuario.
from app.modelos import catalogos, logistica, requerimiento, seguridad  # noqa: F401
from app.modelos.presupuesto import CargaDatos
from app.servicios.seguridad import bitacora
from app.servicios.seguridad.bitacora import Contexto

URL_ARCHIVO = "https://fs.datosabiertos.mef.gob.pe/datastorefiles/{anio}-Gasto-Diario.zip"
SEC_EJEC_UCHUMAYO = "300354"  # Municipalidad Distrital de Uchumayo (ubigeo 040124)
ACTOR = "EXTRACCION_MEF"
LIMA = ZoneInfo("America/Lima")
COLUMNAS_REQUERIDAS = ("SEC_EJEC", "SEC_FUNC", "META_NOMBRE", "MONTO_PIM", "MONTO_CERTIFICADO",
                       "MONTO_COMPROMETIDO_ANUAL")
REINTENTOS = 3
ESPERA_ENTRE_INTENTOS = 30  # segundos


class ErrorExtraccion(Exception):
    """La fuente no respondió o cambió de formato: la carga queda FALLIDA."""


class Fuente(Protocol):
    def ultima_modificacion(self, url: str) -> datetime: ...
    def descargar(self, url: str, destino: Path) -> None: ...


def _con_reintentos(accion: Callable[[], object], descripcion: str,
                    espera: float = ESPERA_ENTRE_INTENTOS) -> object:
    ultimo: Exception | None = None
    for intento in range(1, REINTENTOS + 1):
        try:
            return accion()
        except Exception as error:  # noqa: BLE001 - se reintenta cualquier falla de red
            ultimo = error
            if intento < REINTENTOS:
                time.sleep(espera * intento)
    raise ErrorExtraccion(f"{descripcion}: {ultimo}") from ultimo


class FuenteHttp:
    """Descarga desde el portal del MEF con tiempo máximo y tres intentos (P5, RF-14)."""

    def __init__(self, espera: float = ESPERA_ENTRE_INTENTOS) -> None:
        import requests

        self._http = requests.Session()
        self._http.headers["User-Agent"] = "SistemaValidacionPrevia-Uchumayo/1.0 (RF-14)"
        self._espera = espera

    def ultima_modificacion(self, url: str) -> datetime:
        def consultar() -> datetime:
            r = self._http.head(url, timeout=(30, 60), allow_redirects=True)
            r.raise_for_status()
            return parsedate_to_datetime(r.headers["Last-Modified"])

        return _con_reintentos(consultar, "No se pudo consultar el archivo del MEF",
                               self._espera)  # type: ignore[return-value]

    def descargar(self, url: str, destino: Path) -> None:
        def bajar() -> None:
            with self._http.get(url, stream=True, timeout=(30, 120)) as r:
                r.raise_for_status()
                with open(destino, "wb") as archivo:
                    for bloque in r.iter_content(chunk_size=1 << 20):
                        archivo.write(bloque)

        _con_reintentos(bajar, "No se pudo descargar el archivo del MEF", self._espera)


def fecha_corte(publicado: datetime) -> datetime:
    """El archivo publicado un día trae lo registrado en el SIAF hasta el día anterior,
    igual que la «Última actualización» que muestra la Consulta Amigable."""
    dia = publicado.astimezone(LIMA).date() - timedelta(days=1)
    return datetime(dia.year, dia.month, dia.day, tzinfo=LIMA)


@dataclass
class Meta:
    codigo: str
    nombre: str
    pim: Decimal
    certificacion: Decimal
    compromiso_anual: Decimal


def saldos_por_meta(archivo_zip: Path | BinaryIO, sec_ejec: str = SEC_EJEC_UCHUMAYO) -> list[Meta]:
    """Suma, por meta, el PIM, la certificación y el compromiso anual de la ejecutora.

    El archivo tiene una fila por mes, clasificador y fuente de financiamiento; los montos
    anuales (PIM, certificación, compromiso anual) se suman sobre todas las filas de la meta.
    Solo se decodifican las líneas que contienen el código de la ejecutora: así se recorren
    ~10 millones de filas en menos de un minuto.
    """
    try:
        contenedor = zipfile.ZipFile(archivo_zip)
    except zipfile.BadZipFile as error:
        raise ErrorExtraccion("El archivo del MEF no es un ZIP válido.") from error
    with contenedor, contenedor.open(contenedor.namelist()[0]) as datos:
        cabecera = next(csv.reader([datos.readline().decode("utf-8-sig")]))
        faltan = [c for c in COLUMNAS_REQUERIDAS if c not in cabecera]
        if faltan:
            raise ErrorExtraccion("Cambió el formato del archivo del MEF; faltan las columnas: "
                                  + ", ".join(faltan) + ".")
        pos = {c: cabecera.index(c) for c in COLUMNAS_REQUERIDAS}
        marca = f'"{sec_ejec}"'.encode()
        sumas: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0)] * 3)
        nombres: dict[str, str] = {}
        for linea in datos:
            if marca not in linea:
                continue
            fila = next(csv.reader([linea.decode("utf-8")]))
            if fila[pos["SEC_EJEC"]] != sec_ejec:
                continue
            codigo = fila[pos["SEC_FUNC"]].strip().zfill(4)
            nombres[codigo] = fila[pos["META_NOMBRE"]].strip()[:250]
            try:
                for i, columna in enumerate(COLUMNAS_REQUERIDAS[3:]):
                    sumas[codigo][i] += Decimal(fila[pos[columna]] or "0")
            except InvalidOperation as error:
                raise ErrorExtraccion(f"Monto no numérico en la meta {codigo}.") from error
    if not sumas:
        raise ErrorExtraccion(f"El archivo del MEF no tiene registros de la ejecutora {sec_ejec}.")
    # Una meta sin PIM no puede financiar ningún requerimiento: no se ofrece al registrar.
    return [Meta(c, nombres[c], *sumas[c]) for c in sorted(sumas) if sumas[c][0] > 0]


def a_csv(metas: list[Meta]) -> str:
    """Mismo formato que la carga CSV de respaldo, para pasar por la misma validación."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(COLUMNAS["MEF"])
    for m in metas:
        escritor.writerow([m.codigo, m.nombre, f"{m.pim:.2f}", f"{m.certificacion:.2f}",
                           f"{m.compromiso_anual:.2f}"])
    return salida.getvalue()


@dataclass
class ResultadoExtraccion:
    resultado: str  # EXITOSA, RECHAZADA, FALLIDA o SIN_CAMBIOS
    mensaje: str
    id_carga: int | None = None
    metas: int = 0


def _ultima_automatica(sesion: Session, anio: int) -> CargaDatos | None:
    return sesion.scalar(
        select(CargaDatos).where(
            CargaDatos.fuente == "MEF", CargaDatos.anio_fiscal == anio,
            CargaDatos.origen == "AUTOMATICA", CargaDatos.resultado == "EXITOSA")
        .order_by(CargaDatos.fecha_corte.desc(), CargaDatos.id_carga.desc()).limit(1))


def _bitacora(sesion: Session, momento: datetime, carga: CargaDatos, filas: int, url: str) -> None:
    bitacora.registrar(
        sesion, momento, Contexto(id_traza=uuid.uuid4()), "EXTRACCION_DATOS",
        "EXITO" if carga.resultado == "EXITOSA" else "ERROR", actor_servicio=ACTOR,
        recurso_tipo="CARGA", recurso_id=carga.id_carga,
        detalle={"fuente": "MEF", "origen": "AUTOMATICA", "anio_fiscal": carga.anio_fiscal,
                 "resultado": carga.resultado, "filas": filas, "url": url,
                 "fecha_corte": carga.fecha_corte.date().isoformat() if carga.fecha_corte
                 else None})


def ejecutar(sesion: Session, anio: int, momento: datetime, fuente: Fuente | None = None, *,
             archivo: Path | None = None, corte: date | None = None) -> ResultadoExtraccion:
    """Extrae, valida y registra la base presupuestal del año; nunca deja una carga a medias."""
    url = URL_ARCHIVO.format(anio=anio)
    try:
        if archivo is not None:  # carga manual de un ZIP ya descargado (pruebas o contingencia)
            if corte is None:
                raise ErrorExtraccion("Con --archivo se debe indicar --corte.")
            fecha = datetime(corte.year, corte.month, corte.day, tzinfo=LIMA)
            metas = saldos_por_meta(archivo)
        else:
            fuente = fuente or FuenteHttp()
            fecha = fecha_corte(fuente.ultima_modificacion(url))
            previa = _ultima_automatica(sesion, anio)
            if previa is not None and previa.fecha_corte >= fecha:  # RI-11: exitosa con corte
                return ResultadoExtraccion(
                    "SIN_CAMBIOS", f"El MEF no publicó datos nuevos (corte vigente: "
                    f"{previa.fecha_corte.astimezone(LIMA):%d/%m/%Y}).", previa.id_carga)
            with tempfile.TemporaryDirectory() as carpeta:
                destino = Path(carpeta) / "gasto.zip"
                fuente.descargar(url, destino)
                metas = saldos_por_meta(destino)
    except ErrorExtraccion as error:
        carga = CargaDatos(fuente="MEF", origen="AUTOMATICA", anio_fiscal=anio,
                           fecha_ejecucion=momento, fecha_corte=None, resultado="FALLIDA",
                           detalle_error=str(error)[:500])
        sesion.add(carga)
        sesion.flush()
        _bitacora(sesion, momento, carga, 0, url)
        sesion.commit()
        return ResultadoExtraccion("FALLIDA", str(error), carga.id_carga)

    carga = cargar_csv(sesion, "MEF", anio, fecha, a_csv(metas), fecha_ejecucion=momento,
                       confirmar=False, origen="AUTOMATICA")
    filas = len(metas) if carga.resultado == "EXITOSA" else 0
    _bitacora(sesion, momento, carga, filas, url)
    sesion.commit()
    if carga.resultado != "EXITOSA":
        return ResultadoExtraccion(carga.resultado, carga.detalle_error or "", carga.id_carga)
    return ResultadoExtraccion(
        "EXITOSA", f"{len(metas)} metas con corte al {fecha:%d/%m/%Y}.", carga.id_carga,
        len(metas))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extracción de la base presupuestal del MEF")
    parser.add_argument("--anio", type=int, default=datetime.now(LIMA).year)
    parser.add_argument("--archivo", type=Path, help="ZIP ya descargado (opcional)")
    parser.add_argument("--corte", type=date.fromisoformat, help="Fecha de corte del ZIP")
    args = parser.parse_args(argv)
    if args.archivo is not None:
        try:  # solo archivos dentro de la carpeta de trabajo (CWE-22, hallazgo HE-06)
            args.archivo = Path(resolver_ruta_segura(str(args.archivo), os.getcwd(), ".zip"))
        except ValueError as error:
            print(error)
            return 2

    from app.core.db import FabricaSesion

    with FabricaSesion() as sesion:
        r = ejecutar(sesion, args.anio, datetime.now(LIMA), archivo=args.archivo,
                     corte=args.corte)
    print(f"Extracción MEF {args.anio}: {r.resultado}. {r.mensaje}")
    return 0 if r.resultado in ("EXITOSA", "SIN_CAMBIOS") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
