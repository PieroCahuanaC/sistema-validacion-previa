# Validación del usuario por funcionalidad — Incremento 1

**Ambiente:** calidad (https://sistema-validacion-previa.vercel.app) — datos ficticios, completos.
**Usuaria:** Jefa de Planeamiento y Presupuesto, Municipalidad Distrital de Uchumayo.
**Fecha:** 25/10/2026 · **Conduce:** equipo del proyecto · **Modalidad:** la usuaria recorrió el sistema por su cuenta con estos escenarios y remitió capturas (Figuras 19 a 21 del informe de la Práctica 8).

Escala de resultado (indicación del asesor): **Conforme** · **Observado** (funciona, pero pide un cambio) · **Rechazado** (no cumple).

Datos ficticios disponibles: meta 0012 (saldo S/ 31 500), 0021 (saldo S/ 108 700), 0027 (saldo S/ 48 000),
0033 (sin saldo en la base local). Tope de 8 UIT: S/ 44 000.

| N.° | Funcionalidad (RF / CU) | Escenario que realiza la usuaria | Resultado esperado | Resultado | Comentario de la usuaria | Acción del equipo |
|---|---|---|---|---|---|---|
| F1 | Consultar el saldo presupuestal disponible de la meta al registrar (RF-01, RF-02) | Elige la meta 0012 en «Registrar requerimiento» | Muestra S/ 31 500,00, la fecha de corte y la aclaración de que no es dinero en caja | Conforme | Sin observaciones | Ninguna |
| F2 | Registrar el requerimiento por ítems con monto calculado (RF-01, RI-14) | Agrega dos ítems: 800 bolsas de asfalto en frío a S/ 42,50 y 40 galones de imprimante a S/ 95,00 | El monto se calcula solo: S/ 37 800,00 | Conforme | Sin observaciones | Ninguna |
| F3 | Impedir montos mayores a 8 UIT (RI-14) | Cambia la cantidad de asfalto a 1 200 bolsas | Mensaje de tope de 8 UIT y botón «Registrar y validar» deshabilitado | Conforme | Sin observaciones | Ninguna |
| F4 | Semáforo rojo por presupuesto insuficiente (RF-02, RF-03) | Vuelve a 800 bolsas, elige el ítem PAC-001 y registra | Semáforo rojo, motivo «presupuesto insuficiente» y acción «Aplicar ajuste» | Conforme | Sin observaciones | Ninguna |
| F5 | Base de cálculo del semáforo (RF-02) | Revisa el recuadro de cálculo de la P04 | PIM − compromiso anual = saldo, frente al monto evaluado; cifras que reconoce de la Consulta Amigable | Conforme | Sin observaciones | Ninguna |
| F6 | Semáforo verde con saldo suficiente (RF-02, RF-03) | Registra en la meta 0021 un pedido de 200 paquetes de papel bond a S/ 25,00 con el ítem PAC-002 | Semáforo verde y responsable actual: Gerencia de Administración | Conforme | Sin observaciones (conformidad general; sin captura del escenario) | Ninguna |
| F7 | Semáforo ámbar por requerimiento no previsto en el PAC (RF-03) | Registra en la meta 0027 un pedido marcando «No está previsto en el PAC» | Semáforo ámbar y responsable actual: Jefe de Presupuesto | Conforme | Sin observaciones (conformidad general; sin captura del escenario) | Ninguna |
| F8 | Semáforo ámbar por meta sin datos (CU-01, flujo 2a) | Registra un pedido en la meta 0033 | Semáforo ámbar, motivo «sin saldo en la base presupuestal» | Conforme | Sin observaciones (conformidad general; sin captura del escenario) | Ninguna |
| F9 | Etapas del trámite y responsable actual (CU-04; observación del asesor a la P7) | Pulsa la etapa «Registrado» en cualquier requerimiento | Muestra fecha, hora y rol; las etapas futuras aparecen desactivadas | Conforme | Sin observaciones | Ninguna |
| F10 | Carga CSV de respaldo de la base presupuestal (RF-14, riesgo R01) | El equipo demuestra la carga de un CSV con un error (compromiso > certificación) | La carga queda rechazada con el detalle del error y no se carga ningún saldo | No evaluado | — | Se presentará a la usuaria en la sesión de pruebas de la semana 12 (actividad 3.1) |

**Conclusión de la usuaria:** expresó su conformidad general con el incremento, sin solicitar cambios. Resultado: 9 conformes, 0 observadas, 0 rechazadas y 1 no evaluada (F10).

**Observaciones generales:** las capturas evidencian F1 a F5 y el indicador de etapas de F9 (REQ-2026-00003, monto S/ 37 800,00, semáforo rojo frente a un saldo de S/ 31 500,00). F10 se ejecuta por línea de comandos y no formó parte de la sesión.
