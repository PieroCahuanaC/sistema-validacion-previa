# Casos de prueba — Incrementos 1 y 2 (validación presupuestal temprana; seguridad y acceso)

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
