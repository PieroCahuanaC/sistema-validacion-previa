# Casos de prueba — Incremento 1 (validación presupuestal temprana)

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

## Pruebas de integración (componentes unidos, con PostgreSQL)

| ID | Integración que verifica | RF / regla | Entrada | Resultado esperado |
|---|---|---|---|---|
| CP-I01 | API → servicio → BD | RF-01 a RF-03, RI-15 | Requerimiento de 12 750 en meta 0012 | 201, VERDE; 1 historial y 1 validación |
| CP-I02 | API → servicio → BD | RF-02, RF-04 | Requerimiento de 41 250 | 201, ROJO, opciones de ajuste |
| CP-I03 | API → servicio → BD | RF-03 | Sin ítem PAC; meta 0033 sin saldo | NO_PREVISTO_PAC; SIN_DATOS_META |
| CP-I04 | API → servicio → BD | RI-14, RI-15 | Monto de 85 000 | 422 Problem Details; nada guardado |
| CP-I05 | Frontera de la API (DTO) | RNF-03 | Sin ítems, objeto OBRA | 422 con los campos indicados |
| CP-I06 | API → servicio → BD | RI-14 | Meta, PAC o fecha no válidos | 422 con el motivo |
| CP-I07 | API → detalle → BD | CU-04 | Consulta de un requerimiento | Etapas, responsable y base de cálculo |
| CP-I08 | Seguridad → servicio | RBAC, OWASP A01 | Usuario de otra unidad | 404 |
| CP-I09 | API → consultas → BD | RF-01 (P03) | Metas y PAC | Saldo 31 500; 5 ítems |
| CP-I10 | Seguridad | RF-10, RNF-03 | Rol Jefe de Presupuesto | 403 |
| CP-I11 | BD (disparador) | RI-22 | UPDATE a una validación | Rechazado |
| CP-I12 | BD (disparador diferido) | RI-14 | Monto distinto de la suma | Rechazado al confirmar |
| CP-I13 | BD (CHECK) | RI-09 | Compromiso > certificación | Rechazado |
| CP-I14 | Carga CSV → BD | RF-14, R01 | CSV inválido | Carga RECHAZADA, sin saldos |
