# Pruebas no funcionales (Práctica 9, sección 4)

Carga de la base de datos, carga del servidor de aplicación y escaneo de seguridad del ambiente
de calidad. Los criterios son los del plan de pruebas (sección 1.6) y se fijaron antes de medir.

| Prueba | Herramienta | Qué mide | Criterio |
|---|---|---|---|
| Carga de la base de datos (Tabla 10) | pgbench | Consulta del saldo disponible de una meta al azar (`pruebas/carga-bd/saldo.sql`), con 10, 25, 50, 100, 200 y 400 consultas simultáneas, 30 s por nivel. Solo lectura. | p95 ≤ 2 s y menos del 1 % de errores |
| Carga del servidor (Tabla 11, Figura 1) | k6 | Flujo de escritura: abrir la P03, registrar un requerimiento con su semáforo y abrir su detalle (8 usuarios, RNF-01). Flujo de lectura: abrir la P03 con los saldos de todas las metas (25 a 200 usuarios, búsqueda del umbral). 60 s por nivel. | p95 ≤ 3 s y menos del 1 % de errores |
| Seguridad (Tabla 12) | OWASP ZAP 2.17 | Escaneo pasivo del frontend (`zap-baseline`) y de los 34 endpoints de la API a partir de su definición OpenAPI, en modo seguro (`zap-api-scan -S`). | Ningún hallazgo de riesgo alto; los medios se corrigen o se justifican |

## Cómo se ejecutan

En GitHub: **Actions → Pruebas no funcionales → Run workflow**, en la rama `calidad`. Se puede
elegir una sola prueba. Al terminar, la página de la ejecución muestra las tablas y el artefacto
`pruebas-no-funcionales` trae los reportes de pgbench, k6 y ZAP, las tablas en CSV y las figuras.

Secretos del repositorio que usa (nunca se escriben en el código ni se imprimen):

- `DATABASE_URL`: cadena de conexión de calidad (la misma de la extracción del MEF).
- `CARGA_USUARIO` y `CARGA_CLAVE`: usuario de Área Usuaria exclusivo de la prueba de carga, con
  la contraseña temporal ya cambiada.

No conviene lanzarla a las 05:17 ni a las 11:17 (hora de Lima), cuando corre la extracción del
MEF, ni durante una sesión con usuarios.

## Decisiones

- **Los requerimientos de la prueba no se borran.** La validación, el historial y la bitácora son
  de solo inserción (RI-22). Por eso cada requerimiento de la prueba se registra en rojo (con un
  monto mayor que el saldo de la meta de menor saldo y menor que el tope de 8 UIT) y se cierra
  por la vía del propio sistema: ajuste «Ninguna» y anulación (RI-25). Quedan en estado Anulado,
  con la descripción «PRUEBA DE CARGA k6», y se excluyen de los indicadores.
- **En calidad solo escribe el nivel del RNF-01 (8 usuarios).** La búsqueda del umbral (25 a 200
  usuarios) usa el flujo de lectura del mismo proceso, para no llenar calidad con miles de
  requerimientos antes de la sesión de aceptación. La copia local corre la escritura en todos
  los niveles.
- **Se inicia sesión una sola vez.** El token de acceso dura 15 minutos y se comparte entre los
  usuarios virtuales: cientos de inicios de sesión simultáneos medirían Argon2id, no el proceso
  crítico. Por eso cada ejecución de k6 debe durar menos de 14 minutos.
- **Arranque en frío.** El plan gratuito de Render suspende el servicio tras la inactividad; k6
  lo despierta con `/api/v1/salud` antes de medir.
- **La latencia de la base de datos incluye la red** entre el ejecutor de GitHub y Supabase.

## Resultados y re-prueba

Primera ejecución en calidad (18/11/2026, antes de las correcciones) y comparación con la copia
local, antes y después de corregir los defectos DEF-01 a DEF-03 (`defectos.md`):

| Ambiente | Flujo | Usuarios | p95 (s) | % errores | Resultado |
|---|---|---|---|---|---|
| Calidad, antes | Registro con semáforo | 8 | 3,592 | 0,00 % | No cumple el RNF-01 |
| Calidad, antes | Apertura de la P03 | 25 a 200 | — | 96 a 99,8 % | La API deja de responder |
| Calidad, antes | Consulta del saldo (pgbench) | 10 / 25 o más | 0,042 / — | 0 % / 100 % | El pooler en modo sesión admite 15 clientes |
| Local, antes | Registro con semáforo | 8 / 25 / 50 | 0,196 / 0,677 / 39,0 | 0 / 2,2 / 90,5 % | Desde 50 la API se bloquea y no se recupera |
| Local, después | Registro con semáforo | 8 / 25 / 50 / 100 / 150 / 200 | 0,190 / 0,445 / 0,911 / 1,937 / 3,004 / 4,350 | 0 % en todos | Umbral: 100 usuarios; la API sigue respondiendo |
| Local, después | Apertura de la P03 | 25 / 50 / 100 / 150 / 200 | 0,180 / 0,248 / 1,681 / 2,994 / 4,564 | 0 % en todos | Umbral: 150 usuarios |

Después de la corrección, la carga excesiva ya no produce errores ni bloqueos: aumenta el
tiempo de respuesta (las peticiones esperan su turno) y, si la espera pasa de 10 s, la API
responde 503 «Servicio ocupado». La re-prueba en calidad se registra en el informe.

## Comparación local

La misma prueba se corre contra una copia local (API con un proceso de uvicorn y PostgreSQL en
la misma máquina, con los 175 saldos reales del MEF) para separar el efecto del plan gratuito:

```bash
BD_URL=postgresql://svp:svp@localhost:5432/svp_dev sh pruebas/carga-bd/ejecutar.sh
BASE_URL=http://localhost:8000 ORIGEN=http://localhost:4321 USUARIO=... CLAVE=... \
  NIVELES_ESCRITURA=8,25,50,100,150,200 NIVELES_LECTURA= k6 run pruebas/carga-app/flujo.js
python pruebas/resumir.py --bd local=resultados/bd --app local=resultados/app/k6.json
```
