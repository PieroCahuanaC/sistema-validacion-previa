"""Resume las pruebas de carga en las tablas de la Práctica 9 (Tablas 10 y 11, Figura 1).

Uso:
    python resumir.py --bd calidad=resultados/bd --app calidad=resultados/app/k6.json \
        --salida resultados

--bd y --app se pueden repetir con distintas etiquetas (por ejemplo, calidad y local) para
comparar los ambientes en las mismas tablas y figuras. Escribe resumen.md, carga_bd.csv,
carga_app.csv y, si está instalado matplotlib, figura_bd.png y figura_app.png.

Criterios del plan de pruebas (sección 1.6):
    base de datos   p95 ≤ 2 s y menos del 1 % de errores por nivel de consultas simultáneas.
    aplicación      p95 ≤ 3 s y menos del 1 % de errores; el nivel de 8 usuarios del flujo de
                    escritura es el que verifica el RNF-01, los demás buscan el umbral.
"""

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

LIMITE_BD_S = 2.0
LIMITE_APP_S = 3.0
LIMITE_ERRORES = 0.01
USUARIOS_RNF01 = 8
TIPOS_ERROR = {"resp_503_ocupado": "503 servicio ocupado", "resp_5xx_otros": "otros 5xx",
               "resp_4xx": "4xx", "resp_sin_respuesta": "sin respuesta (tiempo agotado)"}
FLUJOS = {"t_registro": "registro con semáforo", "t_formulario": "apertura del formulario P03"}


@dataclass
class Fila:
    etiqueta: str
    flujo: str
    nivel: int
    promedio_s: float | None
    p95_s: float | None
    errores: float
    muestras: int
    limite_s: float
    tipos_error: dict[str, int] | None = None

    @property
    def cumple(self) -> bool:
        return (self.p95_s is not None and self.p95_s <= self.limite_s
                and self.errores < LIMITE_ERRORES)


def percentil(valores: list[float], p: float) -> float:
    """Percentil por el método del rango más cercano, el mismo que reporta k6."""
    ordenados = sorted(valores)
    rango = max(1, math.ceil(p / 100 * len(ordenados)))
    return ordenados[rango - 1]


def leer_bd(etiqueta: str, carpeta: Path) -> list[Fila]:
    filas = []
    for salida in sorted(carpeta.glob("bd_c*.txt"), key=lambda p: int(p.stem[4:])):
        nivel = int(salida.stem[4:])
        texto = salida.read_text(encoding="utf-8", errors="replace")
        latencias, fallidas = [], 0
        for registro in carpeta.glob(f"bd_c{nivel}.[0-9]*"):
            for linea in registro.read_text().splitlines():
                campos = linea.split()
                if len(campos) < 3:
                    continue
                if campos[2].isdigit():
                    latencias.append(int(campos[2]) / 1_000_000)  # microsegundos → s
                else:  # «failed» o «skipped»
                    fallidas += 1
        m = re.search(r"number of failed transactions: (\d+)", texto)
        fallidas = max(fallidas, int(m.group(1))) if m else fallidas
        total = len(latencias) + fallidas
        # Si pgbench no logró abrir las conexiones, no hay transacciones: todo el nivel falla.
        errores = fallidas / total if total else 1.0
        filas.append(Fila(etiqueta, "consulta del saldo", nivel,
                          sum(latencias) / len(latencias) if latencias else None,
                          percentil(latencias, 95) if latencias else None,
                          errores, total, LIMITE_BD_S))
    return filas


def leer_app(etiqueta: str, archivo: Path) -> list[Fila]:
    metricas = json.loads(archivo.read_text(encoding="utf-8"))["metrics"]
    filas = []
    for clave, datos in metricas.items():
        m = re.fullmatch(r"(t_registro|t_formulario)\{scenario:(escritura|lectura)_u(\d+)\}",
                         clave)
        if not m:
            continue
        metrica, flujo, nivel = m.group(1), m.group(2), int(m.group(3))
        valores = datos["values"]
        fallas = metricas.get(f"http_req_failed{{scenario:{flujo}_u{m.group(3)}}}", {})
        errores = fallas.get("values", {}).get("rate", 0.0)
        esc = f"{flujo}_u{m.group(3)}"
        tipos = {nombre: int(metricas.get(f"{clave_k6}{{scenario:{esc}}}", {})
                             .get("values", {}).get("count", 0))
                 for clave_k6, nombre in TIPOS_ERROR.items()}
        muestras = int(valores.get("count", 0))
        if muestras == 0:  # ninguna respuesta medida: el nivel no cumple
            filas.append(Fila(etiqueta, FLUJOS[metrica], nivel, None, None,
                              max(errores, 1.0) if errores == 0 else errores, 0, LIMITE_APP_S,
                              tipos))
            continue
        filas.append(Fila(etiqueta, FLUJOS[metrica], nivel, valores["avg"] / 1000,
                          valores["p(95)"] / 1000, errores, muestras, LIMITE_APP_S, tipos))
    return sorted(filas, key=lambda f: (f.flujo != "registro con semáforo", f.nivel))


def num(valor: float | None, decimales: int = 3) -> str:
    return "—" if valor is None else f"{valor:.{decimales}f}".replace(".", ",")


def pct(valor: float) -> str:
    return f"{valor * 100:.2f} %".replace(".", ",")


def veredicto_app(f: Fila) -> str:
    if f.muestras == 0:
        return "Sin respuestas"
    if f.flujo == "registro con semáforo" and f.nivel == USUARIOS_RNF01:
        return "Sí (RNF-01)" if f.cumple else "No (RNF-01)"
    return "Dentro del umbral" if f.cumple else "Fuera del umbral"


def umbral(filas: list[Fila], unidad: str) -> str:
    """Mayor nivel que cumple, siempre que todos los niveles menores también cumplan."""
    mejor = None
    for f in sorted(filas, key=lambda x: x.nivel):
        if not f.cumple:
            return f"{mejor} {unidad}" if mejor is not None else "ningún nivel probado cumple"
        mejor = f.nivel
    return (f"al menos {mejor} {unidad} (todos los niveles probados cumplen; "
            "no se alcanzó el límite)")


def escribir_csv(ruta: Path, filas: list[Fila], veredicto) -> None:
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        w = csv.writer(archivo)
        w.writerow(["ambiente", "flujo", "nivel", "promedio_s", "p95_s", "errores_pct",
                    "muestras", "cumple"])
        for f in filas:
            w.writerow([f.etiqueta, f.flujo, f.nivel, num(f.promedio_s), num(f.p95_s),
                        f"{f.errores * 100:.2f}", f.muestras, veredicto(f)])


def figura(ruta: Path, filas: list[Fila], limite: float, eje_x: str, titulo: str) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    series: dict[tuple[str, str], list[Fila]] = {}
    for f in filas:
        series.setdefault((f.etiqueta, f.flujo), []).append(f)
    for (etiqueta, flujo), puntos in series.items():
        puntos = [p for p in sorted(puntos, key=lambda x: x.nivel) if p.p95_s is not None]
        if puntos:
            ax.plot([p.nivel for p in puntos], [p.p95_s for p in puntos], marker="o",
                    label=f"p95 — {flujo} ({etiqueta})")
    ax.axhline(limite, color="#B42318", linestyle="--", linewidth=1,
               label=f"Criterio: {num(limite, 0)} s")
    ax.set_xlabel(eje_x)
    ax.set_ylabel("Tiempo de respuesta p95 (s)")
    ax.set_title(titulo)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta)
    plt.close(fig)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bd", action="append", default=[], metavar="ETIQUETA=CARPETA")
    parser.add_argument("--app", action="append", default=[], metavar="ETIQUETA=JSON")
    parser.add_argument("--salida", default="resultados")
    args = parser.parse_args()
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)

    bd = [f for par in args.bd for f in leer_bd(*_par(par))]
    app = [f for par in args.app for f in leer_app(*_par(par))]
    md = ["# Resultados de las pruebas de carga", ""]

    if bd:
        encabezado = ("| Ambiente | Consultas simultáneas | Tiempo promedio (s) | p95 (s) "
                      "| % errores | Transacciones | ¿Cumple? |")
        md += ["## Carga en la base de datos (Tabla 10)", "",
               f"Criterio: p95 ≤ {num(LIMITE_BD_S, 0)} s y menos del 1 % de errores.", "",
               encabezado, "|---|---|---|---|---|---|---|"]
        md += [f"| {f.etiqueta} | {f.nivel} | {num(f.promedio_s)} | {num(f.p95_s)} | "
               f"{pct(f.errores)} | {f.muestras} | {'Sí' if f.cumple else 'No'} |" for f in bd]
        for etiqueta in dict.fromkeys(f.etiqueta for f in bd):
            u = umbral([f for f in bd if f.etiqueta == etiqueta], "consultas simultáneas")
            md.append(f"\nUmbral de la base de datos ({etiqueta}): {u}.")
        escribir_csv(salida / "carga_bd.csv", bd, lambda f: "Sí" if f.cumple else "No")
        if figura(salida / "figura_bd.png", bd, LIMITE_BD_S, "Consultas simultáneas",
                  "Consultas simultáneas vs tiempo de respuesta de la base de datos"):
            md.append("\nFigura: figura_bd.png")
        md.append("")

    if app:
        criterio = (f"Criterio: p95 ≤ {num(LIMITE_APP_S, 0)} s y menos del 1 % de errores. "
                    f"El RNF-01 se verifica con {USUARIOS_RNF01} usuarios en el registro con "
                    "semáforo.")
        encabezado = ("| Ambiente | Flujo | Usuarios concurrentes | Tiempo promedio (s) "
                      "| p95 (s) | % errores | Muestras | ¿Cumple? |")
        md += ["## Carga en el servidor de aplicación (Tabla 11, Figura 1)", "", criterio, "",
               encabezado, "|---|---|---|---|---|---|---|---|"]
        md += [f"| {f.etiqueta} | {f.flujo} | {f.nivel} | {num(f.promedio_s)} | "
               f"{num(f.p95_s)} | {pct(f.errores)} | {f.muestras} | {veredicto_app(f)} |"
               for f in app]
        for etiqueta, flujo in dict.fromkeys((f.etiqueta, f.flujo) for f in app):
            u = umbral([f for f in app if f.etiqueta == etiqueta and f.flujo == flujo],
                       "usuarios concurrentes")
            md.append(f"\nUmbral de la aplicación ({flujo}, {etiqueta}): {u}.")
        con_tipos = [f for f in app if f.tipos_error and any(f.tipos_error.values())]
        if con_tipos:
            md += ["", "Respuestas fallidas por tipo:", "",
                   "| Ambiente | Flujo | Usuarios | " + " | ".join(TIPOS_ERROR.values()) + " |",
                   "|---|---|---|" + "---|" * len(TIPOS_ERROR)]
            md += [f"| {f.etiqueta} | {f.flujo} | {f.nivel} | "
                   + " | ".join(str(f.tipos_error[n]) for n in TIPOS_ERROR.values()) + " |"
                   for f in con_tipos]
        escribir_csv(salida / "carga_app.csv", app, veredicto_app)
        if figura(salida / "figura_app.png", app, LIMITE_APP_S, "Usuarios concurrentes",
                  "Usuarios concurrentes vs tiempo de respuesta"):
            md.append("\nFigura 1: figura_app.png")

    (salida / "resumen.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def _par(texto: str) -> tuple[str, Path]:
    etiqueta, _, ruta = texto.partition("=")
    if not ruta:
        raise SystemExit(f"Use ETIQUETA=RUTA (recibido: {texto}).")
    return etiqueta, Path(ruta)


if __name__ == "__main__":
    main()
