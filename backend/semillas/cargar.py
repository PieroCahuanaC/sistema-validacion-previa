"""Carga inicial idempotente de catálogos, regla y datos mock (Tabla 24 de la Práctica 6).

Se puede ejecutar varias veces sin duplicar registros. Uso (desde backend/):
    python -m semillas.cargar                      # catálogos + datos mock con corte de ayer
    python -m semillas.cargar --solo-catalogos     # sin datos presupuestales mock
    python -m semillas.cargar --fecha-corte 2026-10-24

Todos los datos son ficticios: no se carga ningún dato personal real (Ley N.° 29733).
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import FabricaSesion
from app.extraccion.carga_csv import cargar_csv
from app.repositorios.presupuesto import RepositorioPresupuesto

LIMA = ZoneInfo("America/Lima")
DATOS = Path(__file__).parent / "datos"

ROLES = [
    ("AU", "Área Usuaria", "Registra y ajusta requerimientos de su unidad"),
    ("GA", "Gerencia de Administración", "Aprueba u observa requerimientos"),
    ("JL", "Jefe de Logística y Abastecimientos", "Valida documentos, cuadro y orden"),
    ("JP", "Jefe de Presupuesto", "Decide ámbar, certifica y configura reglas"),
    ("ADM", "Administrador del sistema", "Gestiona usuarios y roles"),
]
# Unidades orgánicas ficticias para el ambiente de desarrollo y calidad.
UNIDADES = [
    ("Gerencia de Desarrollo Urbano y Rural", "GDUR"),
    ("Gerencia de Servicios Públicos", "GSP"),
    ("Gerencia de Desarrollo Social", "GDS"),
    ("Gerencia de Administración", "GA"),
    ("Sub Gerencia de Abastecimientos y Servicios Generales", "SGASG"),
    ("Oficina de Planeamiento y Presupuesto", "OPP"),
]
# Tabla 14 de la Práctica 6: (orden, código, nombre, plazo en horas, final)
ESTADOS = [
    (1, "REGISTRADO", "Registrado", 24, False),
    (2, "APROBADO", "Aprobado", 24, False),
    (3, "DOCUMENTACION_VALIDADA", "Documentación validada", 120, False),
    (4, "CUADRO_REGISTRADO", "Cuadro comparativo registrado", 48, False),
    (5, "CERTIFICADO", "Certificado", 24, False),
    (6, "ORDEN_EMITIDA", "Orden emitida", None, True),
    (7, "OBSERVADO", "Observado", None, False),
    (8, "ANULADO", "Anulado", None, True),
]
# Tabla 15 de la Práctica 6: (origen, destino, rol, tipo)
TRANSICIONES = [
    ("REGISTRADO", "APROBADO", "GA", "AVANCE"),
    ("REGISTRADO", "OBSERVADO", "GA", "DEVOLUCION"),
    ("APROBADO", "DOCUMENTACION_VALIDADA", "JL", "AVANCE"),
    ("APROBADO", "OBSERVADO", "JL", "DEVOLUCION"),
    ("OBSERVADO", "REGISTRADO", "AU", "AVANCE"),
    ("DOCUMENTACION_VALIDADA", "CUADRO_REGISTRADO", "JL", "AVANCE"),
    ("CUADRO_REGISTRADO", "CERTIFICADO", "JP", "AVANCE"),
    ("CUADRO_REGISTRADO", "DOCUMENTACION_VALIDADA", "JP", "DEVOLUCION"),
    ("CERTIFICADO", "ORDEN_EMITIDA", "JL", "AVANCE"),
    ("REGISTRADO", "ANULADO", "AU", "ANULACION"),
    ("DOCUMENTACION_VALIDADA", "REGISTRADO", "JL", "DEVOLUCION"),
]
TIPOS_DOCUMENTO = [
    "Documento de requerimiento",
    "Cuadro de necesidades",
    "Especificaciones técnicas o términos de referencia",
]
# Tabla 11 de la Práctica 6: valores iniciales; UIT 2026 de S/ 5 500 (D.S. N.° 301-2025-EF).
REGLA_INICIAL = {
    "umbral_disponibilidad_pct": 100,
    "columna_comparacion": "COMPROMISO",
    "tratamiento_no_previsto_pac": "AMBAR",
    "antiguedad_maxima_dias": 7,
    "valor_uit": 5500.00,
}


def cargar_catalogos(sesion: Session) -> None:
    for codigo, nombre, descripcion in ROLES:
        sesion.execute(text(
            "INSERT INTO rol (codigo, nombre, descripcion) VALUES (:c, :n, :d) "
            "ON CONFLICT (codigo) DO NOTHING"), {"c": codigo, "n": nombre, "d": descripcion})
    for nombre, sigla in UNIDADES:
        sesion.execute(text(
            "INSERT INTO unidad_organica (nombre, sigla) VALUES (:n, :s) "
            "ON CONFLICT (nombre) DO NOTHING"), {"n": nombre, "s": sigla})
    for orden, codigo, nombre, plazo, final in ESTADOS:
        sesion.execute(text(
            "INSERT INTO estado (orden, codigo, nombre, plazo_horas, es_final) "
            "VALUES (:o, :c, :n, :p, :f) ON CONFLICT (codigo) DO NOTHING"),
            {"o": orden, "c": codigo, "n": nombre, "p": plazo, "f": final})
    for origen, destino, rol, tipo in TRANSICIONES:
        sesion.execute(text(
            "INSERT INTO transicion (id_estado_origen, id_estado_destino, id_rol, tipo) "
            "SELECT o.id_estado, d.id_estado, r.id_rol, :t FROM estado o, estado d, rol r "
            "WHERE o.codigo = :o AND d.codigo = :d AND r.codigo = :r "
            "ON CONFLICT (id_estado_origen, id_estado_destino) DO NOTHING"),
            {"o": origen, "d": destino, "r": rol, "t": tipo})
    for nombre in TIPOS_DOCUMENTO:
        sesion.execute(text(
            "INSERT INTO tipo_documento (nombre) VALUES (:n) ON CONFLICT (nombre) DO NOTHING"),
            {"n": nombre})
    hay_regla = sesion.scalar(text(
        "SELECT count(*) FROM regla_semaforo WHERE vigente_hasta IS NULL"))
    if not hay_regla:
        sesion.execute(text("INSERT INTO regla_semaforo (parametros) VALUES (CAST(:p AS jsonb))"),
                       {"p": json.dumps(REGLA_INICIAL)})
    sesion.commit()


def cargar_datos_mock(sesion: Session, anio: int, fecha_corte: datetime) -> None:
    repo = RepositorioPresupuesto(sesion)
    archivos = {"MEF": "saldos_mef_mock.csv", "SEACE": "pac_seace_mock.csv"}
    for fuente, archivo in archivos.items():
        if repo.ultima_carga_exitosa(fuente, anio) is None:
            texto = (DATOS / archivo).read_text(encoding="utf-8")
            carga = cargar_csv(sesion, fuente, anio, fecha_corte, texto)
            print(f"  Carga {fuente}: {carga.resultado}")
    # Meta sin saldo en la base local: permite probar el semáforo ámbar SIN_DATOS_META.
    sesion.execute(text(
        "INSERT INTO meta_presupuestal (anio_fiscal, codigo, nombre) "
        "VALUES (:a, '0033', 'Seguridad ciudadana') ON CONFLICT DO NOTHING"), {"a": anio})
    sesion.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solo-catalogos", action="store_true")
    parser.add_argument("--fecha-corte", help="AAAA-MM-DD (por defecto, ayer)")
    parser.add_argument("--anio", type=int, help="Ejercicio fiscal (por defecto, el actual)")
    args = parser.parse_args()

    hoy = datetime.now(LIMA)
    anio = args.anio or hoy.year
    if args.fecha_corte:
        corte = datetime.fromisoformat(args.fecha_corte).replace(tzinfo=LIMA)
    else:
        corte = (hoy - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    with FabricaSesion() as sesion:
        cargar_catalogos(sesion)
        print("Catálogos y regla inicial: listo")
        if not args.solo_catalogos:
            cargar_datos_mock(sesion, anio, corte)
            print(f"Datos mock del ejercicio {anio} con corte {corte.date()}: listo")


if __name__ == "__main__":
    main()
