# Casos de prueba — Incrementos 1 a 4B y correcciones de la Práctica 9 (validación presupuestal; seguridad y acceso; trámite completo; tablero y configuración; extracción automática)

Datos de prueba: mock (semillas). Meta 0012: PIM 180 000, certificación 152 000, compromiso anual
148 500, saldo presupuestal disponible 31 500. Regla inicial: umbral 100 %, columna Compromiso,
no previsto en PAC = ámbar, antigüedad máxima 7 días, UIT S/ 5 500 (tope S/ 44 000).

## Pruebas unitarias (componentes aislados, sin base de datos)

| ID | Componente / función | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-U01 | `evaluar_semaforo` | RF-02, RF-03 | Monto 12 750; saldo 31 500 | VERDE, DISPONIBLE |
| CP-U02 | `evaluar_semaforo` | RF-02, RF-03 | Monto 37 800; saldo 31 500 | ROJO, PRESUPUESTO_INSUFICIENTE |
| CP-U03 | `evaluar_semaforo` | RF-02 | Monto igual al saldo (31 500) | VERDE (caso límite) |
| CP-U04 | `evaluar_semaforo` | CU-01 flujo 2a | Meta sin saldo | AMBAR, SIN_DATOS_META |
| CP-U05 | `evaluar_semaforo` | R-02 | Corte de hace 8 días (máx. 7) | AMBAR, DATO_DESACTUALIZADO |
| CP-U06 | `evaluar_semaforo` | Orden del CU-01 | Dato desactualizado y monto excesivo | DATO_DESACTUALIZADO (prioridad) |
| CP-U07 | `evaluar_semaforo` | RF-03 | No previsto en el PAC | AMBAR, NO_PREVISTO_PAC |
| CP-U08 | `evaluar_semaforo` | RNF-04 | No previsto en PAC, regla en VERDE | VERDE, NO_PREVISTO_PAC |
| CP-U09 | `evaluar_semaforo` | Orden del CU-01 | Monto excesivo y sin PAC | ROJO (prioridad) |
| CP-U10 | `evaluar_semaforo` | RNF-04 | Umbral 110 %, monto 30 000 | ROJO |
| CP-U11 | `calcular_saldo_disponible` | RF-02, RNF-04 | Columna Certificación | Saldo 28 000, ROJO |
| CP-U12 | `opciones_de_ajuste` | RF-04 | ROJO / VERDE | [REFORMULAR, REPROGRAMAR] / [] |
| CP-U13 | `calcular_monto_estimado` | RF-01, RI-14 | 800 × 42,50 + 40 × 95,00 | 37 800,00 |
| CP-U14 | `calcular_monto_estimado` | RI-14 | 3 × 0,335 | 1,01 (redondeo) |
| CP-U15 | `calcular_monto_estimado` | RI-14 | Sin ítems | Error "al menos un ítem" |
| CP-U16 | `verificar_tope_8_uit` | RI-14 | 44 000,00 | Aceptado (límite) |
| CP-U17 | `verificar_tope_8_uit` | RI-14 | 44 000,01 y 0 | Rechazados |
| CP-U18 | `validar_csv` | RF-14 | CSV MEF correcto | Válido |
| CP-U19 | `validar_csv` | RF-14 | CSV con BOM de Excel | Válido |
| CP-U20 | `validar_csv` | RF-14 | Falta una columna | Error de columnas |
| CP-U21 | `validar_csv` | RI-08 | Monto negativo | Error |
| CP-U22 | `validar_csv` | RI-09 | Compromiso > certificación | Error |
| CP-U23 | `validar_csv` | RF-14 | Monto no numérico; código repetido | Dos errores |
| CP-U24 | `validar_csv` | RF-14 | Tipo de objeto del PAC no válido | Error |
| CP-U25 | `validar_csv` | RF-14 | Archivo sin filas | Error |
| CP-U26 | `resolver_ruta_segura` | CWE-22 | Rutas con «..», recorrido parcial y otra extensión | Rechazadas |
| CP-U27 | `semaforo_vigente` | RI-20 | VERDE con cualquier decisión | VERDE |
| CP-U28 | `semaforo_vigente` | RI-20 | ÁMBAR con decisión CONFIRMADA | VERDE |
| CP-U29 | `semaforo_vigente` | RI-20 | ÁMBAR sin decisión; ÁMBAR DENEGADA | AMBAR_PENDIENTE; AMBAR_DENEGADO |
| CP-U30 | `semaforo_vigente` | RI-20 | ROJO | ROJO |
| CP-U31 | `contrasenas.incumplimientos` | RNF-03 | Corta; «Uchumayo2026!»; contiene el usuario; un solo carácter repetido | Regla incumplida en cada caso |
| CP-U32 | `contrasenas.incumplimientos` | RNF-03 | Frase de 28 caracteres | Sin incumplimientos |
| CP-U33 | `contrasenas.hashear` / `verificar` | RNF-03 | Contraseña, otra contraseña, hash mal formado | Hash Argon2id sin texto plano; solo la correcta verifica |
| CP-U34 | `contrasenas.generar_temporal` | CU-15 | 50 generaciones | 50 distintas, 16 caracteres, sin 0/O/o/l/I/1 |
| CP-U35 | `tokens.leer_acceso` | RF-10 | Token a los 14 y a los 15 minutos | Vigente; vencido (reloj inyectado) |
| CP-U36 | `tokens.leer_acceso` | RNF-03, OWASP A07 | Token alterado, firmado con otra clave, basura | Rechazados |
| CP-U37 | `tokens.nuevo_token_renovacion` | RNF-03 | Token nuevo | Solo se guarda su SHA-256 |
| CP-U38 | `Situacion.horas_en_etapa` / `excedido` | RF-07, P08 | Registrado sin enviar; enviado hace 25 h y hace 2 h | Sin plazo; excedido; dentro del plazo |
| CP-U39 | `Situacion.excedido` | RF-07 | Aprobado con 30 h; Documentación validada con 30 h; Observado | Excedido; dentro de 120 h; sin plazo |
| CP-U40 | Acciones de `Situacion` | RF-04, RI-25 | Rojo sin ajuste; Rojo con Ninguna; Ámbar denegado; Observado; Verde enviado | Ajustar; anular; anular; subsanar; en bandeja |
| CP-U41 | `cifrado.cifrar` / `descifrar` | Ley 29733 | Nombre de persona natural cifrado dos veces; texto de 300 caracteres | Valores distintos (nonce), sin texto plano, descifra igual; cabe en 500 |
| CP-U42 | `cifrado.descifrar` | RNF-03 | Valor cifrado alterado; texto no cifrado | «no disponible» (etiqueta GCM); se devuelve igual |
| CP-U43 | `cifrado.resumen_ruc` | RNF-03 | RUC | HMAC de 64 caracteres, determinista y distinto de un SHA-256 sin clave |
| CP-U44 | `cifrado.ruc_valido` | P10 | RUC válidos, con dígito errado, cortos o con letras | Solo los válidos pasan (módulo 11) |

## Pruebas de integración (componentes unidos, con PostgreSQL)

| ID | Integración que verifica | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-I01 | API → servicio → BD | RF-01 a RF-03, RI-15 | Requerimiento de 12 750 en meta 0012 | 201, VERDE; 1 historial y 1 validación |
| CP-I02 | API → servicio → BD | RF-02, RF-04 | Requerimiento de 41 250 | 201, ROJO, opciones de ajuste |
| CP-I03 | API → servicio → BD | RF-03 | Sin ítem PAC; meta 0033 sin saldo | NO_PREVISTO_PAC; SIN_DATOS_META |
| CP-I04 | API → servicio → BD | RI-14, RI-15 | Monto de 85 000 | 422 Problem Details; nada guardado |
| CP-I05 | Frontera de la API (DTO) | RNF-03 | Sin ítems, objeto OBRA | 422 con los campos indicados |
| CP-I06 | API → servicio → BD | RI-14 | Meta, PAC o fecha no válidos | 422 con el motivo |
| CP-I07 | API → detalle → BD | CU-04 | Consulta de un requerimiento verde sin enviar | Etapas, base de cálculo; responsable Área Usuaria (completar el paso 2) |
| CP-I08 | Seguridad → servicio | RBAC, OWASP A01 | Usuario de otra unidad | 404 |
| CP-I09 | API → consultas → BD | RF-01 (P03) | Metas y PAC | Saldo 31 500; 5 ítems |
| CP-I10 | Seguridad | RF-10, RNF-03 | Rol Jefe de Presupuesto | 403 |
| CP-I11 | BD (disparador) | RI-22 | UPDATE a una validación | Rechazado |
| CP-I12 | BD (disparador diferido) | RI-14 | Monto distinto de la suma | Rechazado al confirmar |
| CP-I13 | BD (CHECK) | RI-09 | Compromiso > certificación | Rechazado |
| CP-I14 | Carga CSV → BD | RF-14, R01 | CSV inválido | Carga RECHAZADA, sin saldos |

## Registro en dos pasos (cambio 15 de la Práctica 7)

| ID | Integración que verifica | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-I15 | API → servicio → BD | RF-01 (paso 2) | Guardar solo el plazo de entrega | 200; datos guardados, sin enviar |
| CP-I16 | API → servicio → BD | RF-01, RI-20 | Paso 2 completo, tres documentos, semáforo verde | 200; fecha de envío; responsable Gerencia de Administración |
| CP-I17 | API → servicio → BD | RF-01 | Envío sin un documento; envío sin especificación ni lugar | 422 con lo que falta; nada enviado |
| CP-I18 | API → servicio → BD | RI-20 | Paso 2 con semáforo rojo y con ámbar sin decisión | 409 «solo con semáforo vigente verde» |
| CP-I19 | API → detalle → BD | RI-20, CU-06 | Ámbar confirmado por Presupuesto | Semáforo vigente verde; paso 2 habilitado |
| CP-I20 | API → servicio → BD | RF-01 | Segundo envío; edición después del envío | 409 |
| CP-I21 | API y BD (CHECK) | RI-28 | Ítem de otro requerimiento; fecha de envío sin paso 2 | 422; rechazado por la base de datos |


## Incremento 2: inicio de sesión, gestión de usuarios e inicio (CU-09, CU-15; P01, P02, P16)

Cada prueba crea su propio usuario con una contraseña aleatoria generada al ejecutar la prueba:
no hay contraseñas escritas en el repositorio. El reloj del servidor se inyecta y la prueba lo
adelanta para verificar vencimientos y el fin del bloqueo.

| ID | Integración que verifica | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-I22 | API → autenticación → BD | RF-10, CU-09 | Usuario y contraseña correctos | 200; cookies HttpOnly y SameSite=Strict; bitácora LOGIN_EXITOSO |
| CP-I23 | Seguridad | RF-10, RNF-03 | Sin cookie; cookie falsificada | 401 |
| CP-I24 | API → autenticación → BD | CU-09 flujo 2a | Usuario inexistente; tres contraseñas incorrectas; contraseña correcta durante y después del bloqueo | 401 sin pistas; 401 con 2 y 1 intentos; 423; 423; 200 a los 15 min |
| CP-I25 | API → autenticación → BD | CU-09 flujo 3a | Ingreso con contraseña temporal; nueva contraseña débil; nueva válida | 403 en otras pantallas; 422 con reglas; 204 y acceso normal |
| CP-I26 | API → autenticación → BD | RNF-03, OWASP A07 | Renovación; reuso del token ya rotado | 204 con token nuevo; 401 y todas las sesiones revocadas |
| CP-I27 | API → autenticación | RF-10 | Acceso a los 16 min; renovación; renovación a las 8 h | 401; 204 y acceso; 401 |
| CP-I28 | API → autenticación → BD | RF-10 | Cerrar sesión; reuso de la cookie de acceso copiada | 204; 401 |
| CP-I29 | Middleware de origen | RNF-03 (CSRF) | POST con Origin ajeno; con el origen del frontend | 403; 200 |
| CP-I30 | Bitácora → BD | RNF-03, RI-22 | Ingreso fallido y exitoso | Cadena de hashes íntegra; ninguna contraseña registrada |
| CP-I31 | Seguridad | RF-15 | P16 con AU, GA, JL, JP y ADM | 403 para los cuatro primeros, registrado como ACCESO_DENEGADO; 200 para ADM |
| CP-I32 | API → usuarios → BD | RF-15, RI-13 | AU sin unidad; usuario con DNI; alta correcta; duplicado | 422; 422; 201 con temporal de 16 caracteres; 409 |
| CP-I33 | API → usuarios → BD | RF-15 | Cambio de rol de un usuario con sesión abierta | Sesión cerrada; nuevo rol en el siguiente ingreso |
| CP-I34 | API → usuarios → BD | CU-15 | Restablecer a un usuario bloqueado | Desbloqueado; la contraseña anterior deja de servir; nueva temporal |
| CP-I35 | API → usuarios → BD | RI-06, Ley 29733 | Baja; segunda baja; baja, modificación y restablecimiento de la propia cuenta | Seudónimo y sesiones cerradas; 409; 409 (separación de funciones, P5) |
| CP-I36 | API → inicio → BD | P02 | Inicio del Área Usuaria y de la Gerencia de Administración | Tarjetas y pendientes («Completar paso 2»); GA sin tarjetas |

## Incremento 3, parte A: trámite del Área Usuaria, la Gerencia y las alertas (P04, P05, P07, P08, P11, P17)

Datos: la meta 0012 tiene saldo (verde), la 0015 tiene S/ 2,400.00 disponibles (un
requerimiento de S/ 3,500.00 resulta en rojo) y la 0033 no tiene saldo (ámbar SIN_DATOS_META).

| ID | Integración que verifica | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-I37 | API → máquina de estados → BD | CU-11, RF-13 | Gerencia aprueba un verde enviado | Aprobado; sale de la bandeja; responsable Logística; bitácora CAMBIO_ETAPA |
| CP-I38 | Máquina de estados | RF-05, RNF-03 | Aprobar sin envío; AU y JL aprueban; transición inexistente; aprobar un rojo | 409; 403 con ACCESO_DENEGADO; 409; 409 |
| CP-I39 | API → máquina de estados → BD | CU-11 flujo 2a | Observar sin texto; con texto; subsanar | 422; Observado con la observación visible al área; vuelve a la bandeja |
| CP-I40 | API → ajuste → semáforo → BD | CU-05, RF-04 | Reformular: reducir un ítem y quitar otro | Monto recalculado, nueva validación verde, ajuste y bitácora con ítems anteriores; segundo ajuste 409 |
| CP-I41 | Servicio de ajuste | RI-26 | Bajar el precio de un ítem conservado; subir cantidad; sin cambios; ítem nuevo incompleto; reemplazo | 422 en los cuatro primeros; el reemplazo procede |
| CP-I42 | API → ajuste → máquina de estados | CU-05 flujo 3a, RI-25 | Fecha anterior; anular con opciones; reprogramar; Ninguna; anular | 422; 409; revalida en rojo; solo queda anular; Anulado sin pendientes |
| CP-I43 | API → decisión → BD | CU-06, RF-09, RI-20 | Ámbar en el panel; AU decide; JP confirma; segunda decisión | En la pestaña Ámbar y en la P02 de JP; 403; vigente verde y llega a la bandeja; 409 |
| CP-I44 | API → decisión → máquina de estados | CU-06, RI-25 | Denegar sin sustento; con sustento; anular | 422; Ámbar denegado; Anulado |
| CP-I45 | API → listas | CU-04, RF-03 | P17 con filtro Rojo, buscador, otra unidad, filtro inválido, rol GA | Acción «Aplicar ajuste»; un resultado; no lo ve; 422; 403 |
| CP-I46 | API → historial | CU-10, RF-05 a RF-07 | Historial tras la aprobación, por GA, JP y otra unidad | Línea de tiempo con roles, duración y etapas futuras; 404 para otra unidad |
| CP-I47 | Seguridad | Matriz de permisos (P5) | Detalle por GA, JL, JP y ADM; ajuste por GA | 200 sin acciones del área; 403; 403 |
| CP-I48 | API → inicio | P02 | Inicio de la Gerencia con un requerimiento enviado | Pendiente «Aprobar u observar» que abre la P08 |

## Incremento 3, parte B: Logística y certificación (P09, P10, P12, P13)

| ID | Integración que verifica | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-I49 | API → revisión → máquina de estados → BD | CU-07, RF-11 | Expediente aprobado; tres documentos conformes | En la lista de Logística; Documentación validada; pendiente «Registrar cuadro comparativo»; bitácora REVISION_DOCUMENTO |
| CP-I50 | API → revisión | CU-07 flujo 2a, RI-11 | Observado sin texto; revisión incompleta; rol GA; observado con texto; segunda revisión | 422; 422; 403; Observado con la observación y la etapa de Logística marcada; 409 |
| CP-I51 | API → cuadro → proveedores → BD | CU-08, RF-12, Ley 29733 | Cuadro con persona natural y jurídica, precio menor al validado | Pasa a Presupuesto sin revalidar; RUC y nombre de la persona natural cifrados; Logística los ve, Presupuesto no; búsqueda por RUC; bitácora sin datos personales |
| CP-I52 | Servicio de cuadro | CU-08 flujo 1a | Antes de validar documentos; sin cotizaciones; RUC inválido; persona natural con RUC 20; proveedor repetido; fecha futura; rol JP | 409; 422 en los cinco casos; 403 |
| CP-I53 | API → cuadro → semáforo | Cambio 8 de la P7 | Precio de mercado mayor al monto, con saldo | Revalida en verde con el precio como monto evaluado; pasa a Presupuesto |
| CP-I54 | API → cuadro → semáforo → máquina de estados | Cambio 8 de la P7 | Precio de mercado sin saldo | Revalida en rojo; vuelve a Registrado con «Aplicar ajuste» y la observación de Logística |
| CP-I55 | API → máquina de estados | CU-13, CU-14, RF-05, RF-07 | Pendiente de JP; certificar por JL; certificar por JP; orden por JP; orden por JL; anular cerrado | Lista de 48 h; 403; Certificado; 403; Orden emitida con tiempos y sin etapas futuras; 409 |
| CP-I56 | API → máquina de estados → cuadro | Cambio 4 de la P7, R26 | Devolución sin texto; con texto; corrección del cuadro | 422; modo corrección con la observación de Presupuesto; el mismo cuadro corregido y la bitácora con el valor anterior |
| CP-I57 | API → cuadro → decisión → máquina de estados | Cambio 16 de la P7, RI-20 | Ámbar con el precio de mercado; certificar; denegar; anular sin y con motivo | Pasa a Presupuesto en ámbar; 409; pendiente «Anular por falta de disponibilidad»; 422; Anulado |

## Incremento 4A: tablero, reglas del semáforo y base presupuestal (P06, P14, P15)

| ID | Componente | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-U45 | Orden del tablero | CU-02, P06 | Filas de dos metas, una sin saldo; orden por monto y por tiempo descendente | Meta, saldo y fecha de necesidad; sin saldo o sin tiempo («—») siempre al final |
| CP-U46 | Filtros y tarjetas del tablero | CU-02, H7 | Verde con cuello de botella, observado, cerrado, rojo y ámbar | El observado no cuenta por color; el cerrado va aparte; conteos 4 en trámite, 1 de cada tipo |
| CP-U47 | `ParametrosSemaforo` y cambios entre versiones | CU-12, RNF-04 | Umbral 99 y 201; antigüedad 0 y 32; UIT 0 y con tres decimales; valores fuera de lista; parámetro extra | Rechazados; 5500.0 y «5500.00» no son un cambio; se listan solo los parámetros modificados |
| CP-U48 | `validar_csv` con un CSV de Excel en español | RF-14, R01 | Punto y coma, coma decimal y punto de miles; descripción con coma | Se acepta: 180.000,50 se lee como 180000.50 y la coma del texto se conserva |

| ID | Integración que verifica | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-I58 | API → tablero → situaciones en lote → BD | CU-02, RF-06, RF-08 | Área Usuaria de GDUR y de GSP; Gerencia con filtros de código, semáforo, meta, orden y página | Cada unidad ve solo lo suyo; saldo 31 500 de la meta 0012; sin enviar no corre el plazo; filtros y orden correctos |
| CP-I59 | API → tablero (cuello de botella) | CU-02 flujo 2a, H3 | Requerimiento enviado, consultado 30 h después; Administrador; semáforo «AZUL» | Marcado como cuello de botella (30 h frente a 24 h) y contado en la tarjeta; 403; 422 |
| CP-I60 | API → reglas | CU-12, RNF-04 | Otros roles; umbral 250; mismos valores que la vigente | 403; 422; 409 «sin cambios», sin versión nueva |
| CP-I61 | API → reglas → validación → bitácora | CU-12, RI-10, R14, I-14 | UIT 5 350 y antigüedad 5; pedido de S/ 43 000 | Versión nueva vigente y la anterior cerrada; el tope pasa a S/ 42 800 y rechaza el pedido; las validaciones anteriores conservan su versión; bitácora CONFIG_REGLA con valor anterior y nuevo |
| CP-I62 | API → base presupuestal (vista previa) | RF-14, R01, H9 | Otros roles; CSV con errores; sin columnas; fechas futuras o fuera del año; CSV válido de 2025 | 403; errores por fila y columna; 422; vista previa con avisos (dato desactualizado, metas nuevas) y sin escribir nada |
| CP-I63 | API → carga CSV → base presupuestal → bitácora | RF-14, RI-17 | Carga válida; carga con corte anterior; carga con corte posterior sin una meta; PAC | Carga vigente con bitácora EXTRACCION_DATOS; la de corte anterior queda en el historial sin cambiar la base; la posterior desactiva la meta que ya no figura |
| CP-I64 | API → carga CSV rechazada; estado de las fuentes | RF-14, RI-11 | CSV con compromiso mayor que la certificación; contenido vacío; consulta 10 días después del corte | 422, carga RECHAZADA sin fecha de corte en el historial; 422; MEF marcado como desactualizado (11 días) |

## Incremento 4B: extracción automática de la base presupuestal del MEF (RF-14)

| ID | Componente | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-U49 | `saldos_por_meta` | RF-14 | ZIP con dos meses de una meta, otra meta, una meta sin PIM y filas de otras ejecutoras que contienen «300354» en otra columna | Suma por meta solo de la ejecutora 300354; código con cuatro dígitos; la meta sin PIM se omite; el resultado pasa la validación del CSV |
| CP-U50 | `saldos_por_meta` ante un formato inesperado | R01 | Falta una columna; ninguna fila de la ejecutora; monto no numérico; página HTML en lugar del ZIP | `ErrorExtraccion` con el motivo |
| CP-U51 | Fecha de corte, reintentos y ruta del archivo | RF-14, R01, CWE-22 | Publicación del 17/11 a las 08:48 y a las 22:00 de Lima; dos fallas y un éxito; tres fallas; `--archivo /etc/passwd` | Corte al 16/11; éxito al tercer intento; error tras tres intentos; ruta rechazada (código 2) |

| ID | Integración que verifica | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-I65 | Extracción → carga → base presupuestal → bitácora | RF-14 | Publicación nueva; luego la misma publicación | Carga AUTOMATICA vigente con dos metas y bitácora del actor EXTRACCION_MEF; la segunda vez «sin cambios», sin descargar |
| CP-I66 | Extracción ante la caída o el cambio de la fuente | R01 | Descarga agotada; archivo con otras columnas | Carga FALLIDA con el motivo y bitácora ERROR; la carga vigente no cambia |
| CP-I67 | Extracción con datos incoherentes; contingencia con ZIP local | RI-09, RF-14 | Certificación mayor que el PIM; ZIP local con corte posterior sin una meta; ZIP sin fecha de corte | RECHAZADA sin saldos; la carga local pasa a vigente y desactiva la meta ausente; sin corte, FALLIDA |


## Correcciones de la Práctica 9 (defectos DEF-01 a DEF-06, ver `defectos.md`)

| ID | Componente | RF / regla | Técnica | Entrada | Resultado esperado |
|---|---|---|---|---|---|
| CP-U52 | `LimiteDeConcurrencia` | DEF-01, RNF-01 | Caja negra | Dos turnos; cuatro peticiones lentas a la vez y una a `/salud`; luego dos más | Dos 200 y dos 503 «Servicio ocupado» con `Retry-After: 5`; `/salud` responde sin esperar; liberados los turnos, vuelve a atender |
| CP-U53 | `argumentos_del_motor` | DEF-03 | Caja blanca (ramas) | Pooler en el puerto 6543 y 5432; puerto por defecto; modo forzado a sí y a no; sin cadena | Sentencias preparadas desactivadas solo en modo transacción; pool 4 + 6; turnos = conexiones |
| CP-U54 | `CabecerasDeSeguridad` | DEF-05, OWASP A05 | Caja negra | Respuesta de la API con su propio `Cache-Control`; respuesta de `/docs` | `nosniff`, `DENY` y CSP `default-src 'none'` en la API sin reemplazar las del endpoint; `/docs` sin CSP |
| CP-U55 | `validar_csv` | RF-14 | Caja blanca (ramas) | Fila del MEF sin código o sin nombre; fila del PAC sin referencia; valor estimado no numérico | Error con el motivo de cada rama |
| CP-U56 | `resolver_ruta_segura` y línea de comandos de la carga CSV | DEF-06, CWE-22 | Caja blanca (ramas) | ZIP dentro de la carpeta con extensión `.zip` y `.csv`; argumentos incompletos; fuente desconocida; ruta `../` | ZIP aceptado como `.zip` y rechazado como `.csv`; código 2 sin abrir la base |
| CP-U57 | `FuenteHttp.ultima_modificacion` | RF-14, R01 | Caja blanca (ramas) | Una falla de red y luego `Last-Modified` | Fecha leída al segundo intento; tiempo máximo (30, 60) s; agente de usuario propio |
| CP-U58 | `FuenteHttp.descargar` | RF-14, R01 | Caja blanca (ramas) | Descarga en dos bloques; tres respuestas HTTP 503 | Archivo escrito por bloques de 1 MB; `ErrorExtraccion` tras tres intentos |

| ID | Integración que verifica | RF / regla | Técnica | Entrada | Resultado esperado |
|---|---|---|---|---|---|
| CP-I68 | Aplicación completa → cabeceras | DEF-05, OWASP A05 | Caja negra | `/salud` y `/metas` sin sesión | Cabeceras de seguridad y `Cache-Control: no-store` también en el 401 |
| CP-I69 | Aplicación completa → turnos → BD | DEF-01 | Caja negra | Límite registrado; 30 consultas de metas a la vez | Máximo de turnos = 10 conexiones; las 30 terminan con 200 |
| CP-I70 | Línea de comandos → extracción y carga CSV → BD | DEF-06, RF-14 | Caja negra | `mef --anio 2024 --archivo 2024-Gasto-Diario.zip --corte 2024-12-31`; `carga_csv SEACE 2024 ... pac.csv` | Ambas terminan con código 0 y la carga queda EXITOSA |
| CP-I71 | API → máquina de estados → historial | RF-07, CU-02, CU-13 | Caja negra (valores conocidos) | Reloj del servidor: registro a las 0 h, aprobación a las 5 h, documentación a las 15 h, cuadro a las 35 h, certificación a las 50 h y orden a las 80 h | Tiempo hasta la certificación = 50,0 h; tiempo total = 80,0 h |
