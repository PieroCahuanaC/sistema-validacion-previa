"""Carga manual de la base presupuestal por archivo CSV (RF-14; respuesta al riesgo R01).

El archivo se valida completo antes de cargarse: si una fila tiene un error, no se carga
ninguna (la carga queda RECHAZADA con el detalle). Validaciones de la Práctica 6: montos
numéricos y no negativos; compromiso anual <= certificación <= PIM (RI-09).

Uso por línea de comandos (desde backend/):
    python -m app.extraccion.carga_csv MEF 2026 2026-10-24 ruta/saldos.csv
    python -m app.extraccion.carga_csv SEACE 2026 2026-10-24 ruta/pac.csv
"""

import csv
import io
import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos.presupuesto import CargaDatos, MetaPresupuestal, PacItem, SaldoMeta

COLUMNAS = {
    "MEF": ["meta_codigo", "meta_nombre", "pim", "certificacion", "compromiso_anual"],
    "SEACE": ["numero_referencia", "descripcion", "tipo_objeto", "valor_estimado"],
}
TIPOS_OBJETO_PAC = {"BIEN", "SERVICIO", "OBRA", "CONSULTORIA"}


@dataclass
class ResultadoValidacion:
    filas: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.errores and bool(self.filas)


def _monto(valor: str, columna: str, n_fila: int, errores: list[str]) -> Decimal | None:
    try:
        monto = Decimal(valor.strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        errores.append(f"Fila {n_fila}, columna {columna}: '{valor}' no es un monto numérico.")
        return None
    if monto < 0:
        errores.append(f"Fila {n_fila}, columna {columna}: el monto no puede ser negativo.")
        return None
    return monto


def validar_csv(fuente: str, texto: str) -> ResultadoValidacion:
    """Valida el contenido del CSV según la fuente, sin tocar la base de datos."""
    resultado = ResultadoValidacion()
    lector = csv.DictReader(io.StringIO(texto.lstrip("﻿")))
    faltantes = [c for c in COLUMNAS[fuente] if c not in (lector.fieldnames or [])]
    if faltantes:
        resultado.errores.append(f"Faltan las columnas: {', '.join(faltantes)}.")
        return resultado

    claves_vistas: set[str] = set()
    for n_fila, fila in enumerate(lector, start=2):
        if fuente == "MEF":
            limpia = _validar_fila_mef(fila, n_fila, resultado.errores)
            clave = fila["meta_codigo"].strip()
        else:
            limpia = _validar_fila_seace(fila, n_fila, resultado.errores)
            clave = fila["numero_referencia"].strip()
        if clave in claves_vistas:
            resultado.errores.append(f"Fila {n_fila}: el código '{clave}' está repetido.")
            continue
        claves_vistas.add(clave)
        if limpia:
            resultado.filas.append(limpia)
    if not resultado.filas and not resultado.errores:
        resultado.errores.append("El archivo no contiene filas de datos.")
    return resultado


def _validar_fila_mef(fila: dict, n_fila: int, errores: list[str]) -> dict | None:
    codigo, nombre = fila["meta_codigo"].strip(), fila["meta_nombre"].strip()
    if not codigo or not nombre:
        errores.append(f"Fila {n_fila}: el código y el nombre de la meta son obligatorios.")
        return None
    pim = _monto(fila["pim"], "pim", n_fila, errores)
    cert = _monto(fila["certificacion"], "certificacion", n_fila, errores)
    comp = _monto(fila["compromiso_anual"], "compromiso_anual", n_fila, errores)
    if pim is None or cert is None or comp is None:
        return None
    if not comp <= cert <= pim:
        errores.append(
            f"Fila {n_fila}: debe cumplirse compromiso anual <= certificación <= PIM."
        )
        return None
    return {"codigo": codigo, "nombre": nombre, "pim": pim, "certificacion": cert,
            "compromiso_anual": comp}


def _validar_fila_seace(fila: dict, n_fila: int, errores: list[str]) -> dict | None:
    referencia, descripcion = fila["numero_referencia"].strip(), fila["descripcion"].strip()
    tipo = fila["tipo_objeto"].strip().upper()
    if not referencia or not descripcion:
        errores.append(f"Fila {n_fila}: la referencia y la descripción son obligatorias.")
        return None
    if tipo not in TIPOS_OBJETO_PAC:
        errores.append(f"Fila {n_fila}: tipo de objeto '{tipo}' no válido.")
        return None
    valor = _monto(fila["valor_estimado"], "valor_estimado", n_fila, errores)
    if valor is None:
        return None
    return {"numero_referencia": referencia, "descripcion": descripcion, "tipo_objeto": tipo,
            "valor_estimado": valor}


def cargar_csv(
    sesion: Session, fuente: str, anio_fiscal: int, fecha_corte: datetime, texto: str
) -> CargaDatos:
    """Valida y registra la carga en una sola transacción; devuelve la carga creada."""
    validacion = validar_csv(fuente, texto)
    carga = CargaDatos(
        fuente=fuente, origen="MANUAL_CSV", anio_fiscal=anio_fiscal,
        fecha_ejecucion=datetime.now(ZoneInfo("America/Lima")),
        fecha_corte=fecha_corte if validacion.es_valido else None,
        resultado="EXITOSA" if validacion.es_valido else "RECHAZADA",
        detalle_error=None if validacion.es_valido else "; ".join(validacion.errores)[:500],
    )
    sesion.add(carga)
    sesion.flush()
    if validacion.es_valido:
        if fuente == "MEF":
            _persistir_saldos(sesion, carga, validacion.filas)
        else:
            sesion.add_all(PacItem(id_carga=carga.id_carga, **f) for f in validacion.filas)
    sesion.commit()
    return carga


def _persistir_saldos(sesion: Session, carga: CargaDatos, filas: list[dict]) -> None:
    for fila in filas:
        meta = sesion.scalar(
            select(MetaPresupuestal).where(
                MetaPresupuestal.anio_fiscal == carga.anio_fiscal,
                MetaPresupuestal.codigo == fila["codigo"],
            )
        )
        if meta is None:
            meta = MetaPresupuestal(anio_fiscal=carga.anio_fiscal, codigo=fila["codigo"],
                                    nombre=fila["nombre"])
            sesion.add(meta)
            sesion.flush()
        sesion.add(SaldoMeta(id_meta=meta.id_meta, id_carga=carga.id_carga, pim=fila["pim"],
                             certificacion=fila["certificacion"],
                             compromiso_anual=fila["compromiso_anual"]))


def main(argv: list[str]) -> int:
    from app.core.db import FabricaSesion

    if len(argv) != 4 or argv[0] not in COLUMNAS:
        print(__doc__)
        return 2
    fuente, anio, fecha, ruta = argv
    corte = datetime.fromisoformat(fecha).replace(tzinfo=ZoneInfo("America/Lima"))
    with open(ruta, encoding="utf-8") as archivo, FabricaSesion() as sesion:
        carga = cargar_csv(sesion, fuente, int(anio), corte, archivo.read())
    print(f"Carga {carga.id_carga}: {carga.resultado}. {carga.detalle_error or ''}")
    return 0 if carga.resultado == "EXITOSA" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
