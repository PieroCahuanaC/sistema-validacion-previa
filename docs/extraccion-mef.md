# Extracción automática de la base presupuestal (RF-14)

## Qué hace

Dos veces al día (05:17 y 11:17, hora de Lima), el flujo `.github/workflows/extraccion.yml` ejecuta `python -m app.extraccion.mef`. El proceso tiene cinco pasos:

1. Consulta la fecha de publicación del archivo `{año}-Gasto-Diario.zip` del conjunto «Presupuesto y Ejecución de Gasto» del Portal de Datos Abiertos del MEF. El MEF declara que ese conjunto proviene de la Consulta Amigable y lo actualiza todos los días.
2. Si esa publicación ya se cargó, termina **sin cambios** y no descarga nada.
3. Si hay una publicación nueva, descarga el ZIP (unos 600 MB) y lo recorre sin descomprimirlo en disco. Suma por meta (`SEC_FUNC`) el PIM, la certificación y el compromiso anual de la ejecutora **300354** (Municipalidad Distrital de Uchumayo). Las metas sin PIM no se cargan.
4. Pasa el resultado por la misma validación que la carga CSV de respaldo (RI-09, RI-11) y lo registra con origen `AUTOMATICA`. Además, deja el evento `EXTRACCION_DATOS` en la bitácora con el actor de servicio `EXTRACCION_MEF`.
5. Asigna la fecha de corte: el día anterior a la publicación, igual que la «Última actualización» que muestra la Consulta Amigable.

Si la fuente no responde, tras tres intentos con espera creciente, o si cambia el formato del archivo, la carga queda **FALLIDA** y el motivo se guarda en el historial de la P15. Si los datos son incoherentes, por ejemplo una certificación mayor que el PIM, la carga queda **RECHAZADA**. En ambos casos el semáforo sigue usando la última carga exitosa y la ejecución queda en rojo en GitHub Actions, que avisa por correo al dueño del repositorio (plan de respuesta del riesgo R01).

## Por qué no se lee la página de la Consulta Amigable

La Práctica 5 previó leer la página de la Consulta Amigable con `requests` y `BeautifulSoup`. La prueba del 17/11/2026 mostró dos problemas:

- El navegador de la Consulta Amigable llega, para la municipalidad, hasta *Producto/Proyecto* y *Actividad/Acción de inversión/Obra*, pero **no hasta la meta** (secuencia funcional), que es la unidad con la que valida el semáforo.
- La página está detrás de una protección contra robots (Incapsula), que puede bloquear un script en cualquier momento.

El archivo de datos abiertos sí trae la meta (`SEC_FUNC`, `META_NOMBRE`) con sus montos. Sus totales coinciden al céntimo con los de la Consulta Amigable para la ejecutora 300354:

| Concepto (2026, corte 16/11/2026) | Consulta Amigable | Archivo de datos abiertos |
|---|---|---|
| PIA | 44 922 183 | 44 922 183,00 |
| PIM | 125 814 727 | 125 814 727,00 |
| Compromiso anual | 116 171 092,71 | 116 171 092,71 |

Resultado de esa prueba: 201 metas, de las cuales 175 tienen PIM y se cargaron. La ejecución tomó unos 90 segundos, la mayor parte en la descarga.

Este cambio de fuente se registra en el control de cambios de la Fase 3. Ya no se necesita `BeautifulSoup`; se mantiene `requests`.

## PAC del SEACE

No se encontró una fuente pública y legible por un programa del PAC 2026:

- Los archivos de datos abiertos del PAC en CONOSCE llegan hasta 2025 y sus enlaces ya no responden.
- La publicación OCDS del OECE no incluye las líneas del PAC en la etapa de planificación.

Como el PAC solo cambia cuando se aprueba o se modifica, el PAC se sigue cargando con la **carga CSV de respaldo de la P15**.

## Configuración

- **Secreto del repositorio** `DATABASE_URL`: la cadena de conexión del ambiente (calidad). Se define en *Settings → Secrets and variables → Actions*.
- **Ejecución manual**: *Actions → Extracción MEF → Run workflow*.
- **Contingencia con un ZIP ya descargado**: `python -m app.extraccion.mef --anio 2026 --archivo 2026-Gasto-Diario.zip --corte 2026-11-16`. El archivo debe estar dentro de la carpeta de trabajo.

## Fuentes

- Ministerio de Economía y Finanzas. (2026). *Presupuesto y Ejecución de Gasto* [Conjunto de datos]. Portal de Datos Abiertos del MEF. https://datosabiertos.mef.gob.pe/dataset/presupuesto-y-ejecucion-de-gasto
- Ministerio de Economía y Finanzas. (2026). *Consulta Amigable: Consulta de Ejecución del Gasto*. https://apps5.mineco.gob.pe/transparencia/Navegador/default.aspx
