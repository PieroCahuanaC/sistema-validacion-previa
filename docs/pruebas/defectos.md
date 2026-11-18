# Registro de defectos (Práctica 9, sección 5)

Defectos encontrados al ejecutar el plan de pruebas, con su corrección y su re-prueba. Los
defectos de las prácticas anteriores (hallazgos de SonarQube, validación del usuario) están en
los informes de las Prácticas 7 y 8.

Severidad según el plan de pruebas (sección 1.6): crítica (cálculo erróneo o flujo bloqueado),
alta (un RF o RNF no se cumple, con vía alterna), media (no altera los datos), baja (cosmética
o de configuración sin impacto directo).

| ID | Detectado por | Descripción | Severidad | Corrección | Re-prueba |
|---|---|---|---|---|---|
| DEF-01 | Prueba de carga con k6 (local y calidad) | Con 50 usuarios (local) o 25 (calidad) la API deja de responder y no se recupera al terminar la carga. El volcado de hilos mostró los 40 hilos de AnyIO esperando una conexión del pool (15) y las conexiones retenidas por peticiones que esperaban un hilo. | Crítica | Turno de atención (`app/core/middleware.py`): se admiten a la vez tantas peticiones como conexiones tiene el pool; las demás esperan sin ocupar hilos y, pasados 10 s, reciben 503 con `Retry-After`. Pool configurable (`BD_POOL_TAMANO`, `BD_POOL_EXTRA`). | CP-U52, CP-I69 y la prueba de carga local y en calidad (ver `no-funcionales.md`) |
| DEF-02 | Prueba de carga con k6 (calidad) | RNF-01 incumplido: con 8 usuarios, p95 de 3,59 s en el registro con semáforo (local: 0,196 s). Causas: la API (Render, Oregón) y la base (Supabase, Virginia) están en costas distintas, y un registro hacía 19 consultas (unas 21 idas y vueltas). | Alta | Menos consultas: sesión, usuario y rol en una sola; carga y saldo en una sola; la bitácora reutiliza el bloqueo y el registro previo dentro de la transacción (19 → 14 por registro y 2 menos en cada petición autenticada). Mover la API a Virginia (decisión de infraestructura). | Prueba de carga en calidad |
| DEF-03 | Prueba de carga con pgbench (calidad) | El pooler de Supabase en modo sesión admite 15 clientes en total (`EMAXCONNSESSION`): desde 25 consultas simultáneas la base rechaza conexiones, y la API sola puede ocupar las 15 y dejar sin conexión a la extracción del MEF. | Alta | La API admite el pooler en modo transacción (puerto 6543), que multiplexa los clientes sobre las mismas conexiones; con ese puerto se desactivan las sentencias preparadas de psycopg. Pool de la API reducido a 10. | CP-U53 y prueba de carga de la base en calidad |
| DEF-04 | OWASP ZAP (frontend) | Faltan la política de seguridad de contenidos (CSP), Permissions-Policy y las políticas de aislamiento (COOP, COEP); la hoja de estilos de Google Fonts se carga sin integridad (SRI). | Media | Fuente servida desde el propio sitio (`@fontsource/public-sans`); CSP con hashes generada por Astro y cabeceras en `vercel.json`. | Escaneo de ZAP en calidad |
| DEF-05 | OWASP ZAP (API, ensayo local) | La API responde también en su dominio de Render, sin pasar por Vercel, y no envía cabeceras de seguridad propias (`X-Content-Type-Options` ausente). | Baja | Middleware de cabeceras de seguridad en la API (`nosniff`, `DENY`, CSP `default-src 'none'`, `no-store`). | CP-U54, CP-I68 y escaneo de ZAP |
| DEF-06 | Análisis de cobertura de ramas (caja blanca, RF-14) | La contingencia manual de la extracción (`python -m app.extraccion.mef --archivo descarga.zip`) rechazaba siempre el archivo: la verificación de ruta exigía la extensión `.csv`. Además, la carga CSV por línea de comandos abría la base antes de validar los argumentos. | Media | La verificación de ruta recibe la extensión esperada (`.zip` para el MEF); la línea de comandos valida antes de conectarse. | CP-U56 y CP-I70 |

## Fallas de las herramientas de prueba (no son defectos del sistema)

| Herramienta | Falla | Corrección |
|---|---|---|
| OWASP ZAP (API) | En la red por defecto de Docker, ZAP no pudo abrir su puerto interno («Address already in use») y el escaneo de la API no se ejecutó. | Red del host y puerto propio (`-P 8091`). |
| Resumen de resultados | Un nivel sin ninguna respuesta medida aparecía como «dentro del umbral». | Un nivel sin respuestas cuenta como «Sin respuestas» y no cumple. |
| k6 | El resumen no distinguía los tipos de error. | Contadores por tipo: 503, otros 5xx, 4xx y sin respuesta. |
| PyTest (CP-I66, CP-I67) | Fallaban al ejecutarse solos (`pytest -k cpi66`): dependían de la carga vigente que deja CP-I65. En la suite completa pasaban por el orden de ejecución. | Cada caso garantiza su propia carga vigente (`_con_carga_vigente`). Verificado ejecutando las 150 pruebas una por una. |
