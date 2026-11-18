"""Lista los hallazgos de los reportes JSON de OWASP ZAP (Práctica 9, Tabla 12).

Uso: python resumir_zap.py CARPETA   (lee frontend.json y api.json si existen)

Imprime una tabla en Markdown con el riesgo, la CWE y las instancias de cada alerta. La
categoría del OWASP Top 10:2021 se toma de la página de cada alerta en la documentación de ZAP
(enlace en la tabla), no se deduce aquí.
"""

import json
import sys
from pathlib import Path

ESCANEOS = {"frontend.json": "Frontend", "api.json": "API (OpenAPI)"}
ORDEN_RIESGO = {"3": 0, "2": 1, "1": 2, "0": 3}


def main(carpeta: Path) -> None:
    filas = []
    for archivo, escaneo in ESCANEOS.items():
        ruta = carpeta / archivo
        if not ruta.exists():
            continue
        for sitio in json.loads(ruta.read_text(encoding="utf-8")).get("site", []):
            for alerta in sitio.get("alerts", []):
                filas.append((escaneo, alerta))
    print("## Escaneo de seguridad con OWASP ZAP (Tabla 12)\n")
    if not filas:
        print("No se encontraron reportes de ZAP.")
        return
    print("| Escaneo | Hallazgo | Riesgo (confianza) | CWE | Instancias | Documentación |")
    print("|---|---|---|---|---|---|")
    for escaneo, a in sorted(filas, key=lambda f: (ORDEN_RIESGO.get(f[1]["riskcode"], 9),
                                                   f[1]["name"])):
        enlace = f"https://www.zaproxy.org/docs/alerts/{a['alertRef'].split('-')[0]}/"
        print(f"| {escaneo} | {a['name']} | {a['riskdesc']} | CWE-{a['cweid']} | "
              f"{a['count']} | {enlace} |")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
