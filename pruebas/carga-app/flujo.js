// Prueba de carga del servidor de aplicación (Práctica 9, Tabla 11 y Figura 1; RNF-01).
//
// Dos flujos del proceso crítico, la validación presupuestal temprana:
//   escritura  El Área Usuaria abre el formulario P03, registra un requerimiento (el sistema
//              calcula el semáforo; es lo que mide el RNF-01) y abre su detalle. Para no dejar
//              requerimientos abiertos, cada uno se registra en rojo y se cierra por la vía del
//              propio sistema: ajuste «Ninguna» y anulación (RI-25). Ninguno se borra (RI-22).
//   lectura    Solo abre el formulario P03: metas con su saldo disponible, ítems del PAC y regla
//              vigente, que son los datos con los que se calcula el semáforo. No escribe.
// Cada nivel de usuarios concurrentes es un escenario de k6, uno tras otro.
//
// Variables de entorno:
//   BASE_URL            URL del sistema (en calidad, la de Vercel, que reenvía /api a Render).
//   ORIGEN              cabecera Origin (por defecto, BASE_URL).
//   USUARIO, CLAVE      usuario de Área Usuaria exclusivo de la prueba (secretos; no se imprimen).
//   NIVELES_ESCRITURA   usuarios concurrentes del flujo de escritura (por defecto "8").
//   NIVELES_LECTURA     usuarios concurrentes del flujo de lectura (por defecto "25,50,100,150,200").
//   DURACION            segundos por nivel (por defecto 60).
//   PAUSA               segundos de pausa entre iteraciones de cada usuario (por defecto 1).
//   SALIDA              archivo JSON del resumen (por defecto resultados/app/k6.json).
import http from "k6/http";
import { check, fail, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";

const BASE = (__ENV.BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const API = `${BASE}/api/v1`;
const ORIGEN = __ENV.ORIGEN || BASE;
const DURACION = Number(__ENV.DURACION || 60);
const PAUSA = Number(__ENV.PAUSA || 1);
const SEPARACION = 5; // segundos de calma entre niveles
const MARCA = "PRUEBA DE CARGA k6";
const TOPE_MONTO = 43900; // por debajo del tope de 8 UIT (S/ 44 000)

const lista = (texto, porDefecto) =>
  (texto === undefined ? porDefecto : texto)
    .split(",").map((n) => n.trim()).filter((n) => n !== "").map(Number);
const ESCRITURA = lista(__ENV.NIVELES_ESCRITURA, "8");
const LECTURA = lista(__ENV.NIVELES_LECTURA, "25,50,100,150,200");

export const tRegistro = new Trend("t_registro", true); // RNF-01: registro con semáforo
export const tFormulario = new Trend("t_formulario", true); // apertura del formulario P03
const sinCerrar = new Counter("requerimientos_sin_cerrar");
// Respuestas fallidas por tipo, para explicar el % de errores de cada nivel.
export const CODIGOS = {
  ocupado_503: new Counter("resp_503_ocupado"), error_5xx: new Counter("resp_5xx_otros"),
  cliente_4xx: new Counter("resp_4xx"), sin_respuesta: new Counter("resp_sin_respuesta"),
};

function contar(respuesta) {
  const s = respuesta.status;
  if (s === 0) CODIGOS.sin_respuesta.add(1); // tiempo agotado o conexión rechazada
  else if (s === 503) CODIGOS.ocupado_503.add(1);
  else if (s >= 500) CODIGOS.error_5xx.add(1);
  else if (s >= 400) CODIGOS.cliente_4xx.add(1);
}

const nombre = (flujo, n) => `${flujo}_u${String(n).padStart(3, "0")}`;

function construirEscenarios() {
  const escenarios = {};
  const umbrales = {};
  let inicio = 0;
  const agregar = (flujo, n, metrica) => {
    const esc = nombre(flujo, n);
    escenarios[esc] = {
      executor: "constant-vus", exec: flujo, vus: n, duration: `${DURACION}s`,
      startTime: `${inicio}s`, gracefulStop: "10s",
    };
    // Umbrales del plan de pruebas (sección 1.6): p95 ≤ 3 s y menos del 1 % de errores.
    // Se declaran por escenario para que el resumen traiga las cifras de cada nivel.
    umbrales[`${metrica}{scenario:${esc}}`] = ["p(95)<3000"];
    umbrales[`http_req_failed{scenario:${esc}}`] = ["rate<0.01"];
    umbrales[`http_req_duration{scenario:${esc}}`] = ["p(95)<3000"];
    // Umbrales siempre verdaderos: solo hacen que el resumen traiga la cuenta por nivel.
    Object.values(CODIGOS).forEach((c) => { umbrales[`${c.name}{scenario:${esc}}`] = ["count>=0"]; });
    inicio += DURACION + 10 + SEPARACION;
  };
  ESCRITURA.forEach((n) => agregar("escritura", n, "t_registro"));
  LECTURA.forEach((n) => agregar("lectura", n, "t_formulario"));
  // El token de acceso dura 15 minutos y se obtiene una sola vez (iniciar sesión cientos de
  // veces a la vez mediría Argon2id, no el proceso crítico).
  if (inicio > 14 * 60) {
    throw new Error(`La prueba dura ${inicio} s y el token, 15 min: reduzca niveles o DURACION.`);
  }
  return { escenarios, umbrales };
}

const { escenarios, umbrales } = construirEscenarios();

export const options = {
  scenarios: escenarios,
  thresholds: umbrales,
  setupTimeout: "180s",
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "max", "count"],
};

function cabeceras(token) {
  return {
    headers: {
      "Content-Type": "application/json", Origin: ORIGEN,
      Cookie: `svp_acceso=${token}`,
    },
  };
}

export function setup() {
  // Despierta el servicio (el plan gratuito de Render se suspende tras la inactividad) para
  // que el arranque en frío no entre en la medición.
  let listo = false;
  for (let i = 0; i < 18 && !listo; i++) {
    listo = http.get(`${API}/salud`, { timeout: "60s" }).status === 200;
    if (!listo) sleep(5);
  }
  if (!listo) fail("El servicio no respondió en /api/v1/salud.");

  if (!__ENV.USUARIO || !__ENV.CLAVE) fail("Faltan USUARIO y CLAVE.");
  const ingreso = http.post(`${API}/auth/ingreso`,
    JSON.stringify({ nombre_usuario: __ENV.USUARIO, contrasena: __ENV.CLAVE }),
    { headers: { "Content-Type": "application/json", Origin: ORIGEN } });
  if (ingreso.status !== 200) fail(`Ingreso rechazado (HTTP ${ingreso.status}).`);
  if (ingreso.json("contrasena_temporal")) fail("Cambie primero la contraseña temporal.");
  const galleta = ingreso.cookies.svp_acceso;
  if (!galleta || galleta.length === 0) fail("El ingreso no devolvió la cookie de acceso.");
  const token = galleta[0].value;

  // Meta para el flujo de escritura: la de menor saldo, para que el monto la supere sin pasar
  // del tope de 8 UIT y el requerimiento salga en rojo (así se puede anular).
  const metas = http.get(`${API}/metas`, cabeceras(token)).json()
    .filter((m) => m.saldo_disponible !== null)
    .map((m) => ({ codigo: m.codigo, saldo: Number(m.saldo_disponible) }))
    .sort((a, b) => a.saldo - b.saldo);
  if (metas.length === 0) fail("No hay metas con saldo cargado.");
  const meta = metas[0];
  const monto = Math.max(meta.saldo, 0) + 100;
  if (ESCRITURA.length > 0 && monto > TOPE_MONTO) {
    fail(`Ninguna meta tiene saldo menor que S/ ${TOPE_MONTO - 100}: el registro no saldría en rojo.`);
  }
  const hoy = new Date(Date.now() - 5 * 3600 * 1000); // fecha de Lima (UTC−5)
  const necesidad = new Date(hoy.getTime() + 30 * 86400 * 1000).toISOString().slice(0, 10);
  console.log(`Meta de la prueba: ${meta.codigo}; monto S/ ${monto.toFixed(2)}.`);
  return { token, meta: meta.codigo, monto: monto.toFixed(2), necesidad };
}

function abrirFormulario(datos) {
  const opciones = cabeceras(datos.token);
  const inicio = Date.now();
  const respuestas = http.batch([
    ["GET", `${API}/metas`, null, { ...opciones, tags: { paso: "metas" } }],
    ["GET", `${API}/pac-items`, null, { ...opciones, tags: { paso: "pac" } }],
    ["GET", `${API}/regla-vigente`, null, { ...opciones, tags: { paso: "regla" } }],
  ]);
  tFormulario.add(Date.now() - inicio);
  respuestas.forEach(contar);
  check(respuestas, { "formulario P03 cargado": (r) => r.every((x) => x.status === 200) });
}

export function lectura(datos) {
  abrirFormulario(datos);
  sleep(PAUSA);
}

export function escritura(datos) {
  const opciones = cabeceras(datos.token);
  abrirFormulario(datos);

  const cuerpo = {
    meta_codigo: datos.meta, objeto_contratacion: "BIEN",
    descripcion: `${MARCA}: requerimiento ficticio, VU ${__VU}, iteración ${__ITER}`,
    items: [{ descripcion: "Material ficticio de la prueba de carga", unidad_medida: "unidad",
              cantidad: "1", precio_unitario_ref: datos.monto, fuente_precio: "COTIZACION" }],
    fecha_necesidad: datos.necesidad, pac_item_referencia: null,
  };
  const registro = http.post(`${API}/requerimientos`, JSON.stringify(cuerpo),
    { ...opciones, tags: { paso: "registro" } });
  tRegistro.add(registro.timings.duration);
  contar(registro);
  if (!check(registro, { "registro con semáforo (201)": (r) => r.status === 201 })) {
    sleep(PAUSA);
    return;
  }
  const id = registro.json("requerimiento_id");
  const rojo = registro.json("estado_semaforo") === "ROJO";

  const detalle = http.get(`${API}/requerimientos/${id}`, { ...opciones, tags: { paso: "detalle" } });
  contar(detalle);
  check(detalle, { "detalle (200)": (r) => r.status === 200 });

  // Cierre por la vía del sistema: ajuste «Ninguna» y anulación (RI-25).
  let cerrado = false;
  if (rojo) {
    const ajuste = http.post(`${API}/requerimientos/${id}/ajustes`,
      JSON.stringify({ opcion: "NINGUNA" }), { ...opciones, tags: { paso: "ajuste" } });
    contar(ajuste);
    if (check(ajuste, { "ajuste Ninguna (200)": (r) => r.status === 200 })) {
      const anulacion = http.patch(`${API}/requerimientos/${id}/etapa`,
        JSON.stringify({ destino: "ANULADO", observacion: MARCA }),
        { ...opciones, tags: { paso: "anulacion" } });
      contar(anulacion);
      cerrado = check(anulacion, { "anulación (200)": (r) => r.status === 200 });
    }
  }
  if (!cerrado) sinCerrar.add(1);
  sleep(PAUSA);
}

export function handleSummary(datos) {
  const salida = __ENV.SALIDA || "resultados/app/k6.json";
  return {
    [salida]: JSON.stringify(datos, null, 1),
    stdout: `\nResumen guardado en ${salida}\n`,
  };
}
