// Cliente de la API REST /api/v1 (contrato de la Práctica 5). Los errores llegan en formato
// Problem Details; aquí se convierten en un mensaje que la pantalla puede mostrar.
// La sesión viaja en cookies HttpOnly del mismo sitio: este código nunca ve los tokens. Si el
// token de acceso (15 min) venció, se renueva una vez y se repite la petición; si la sesión
// terminó, se vuelve a Iniciar sesión (P01) recordando la pantalla de origen.
const BASE = "/api/v1";

export type Meta = { codigo: string; nombre: string; saldo_disponible: string | null; fecha_corte: string | null };
export type PacItem = { numero_referencia: string; descripcion: string; tipo_objeto: string; valor_estimado: string };
export type ReglaVigente = { valor_uit: string; tope_8_uit: string; antiguedad_maxima_dias: number };
export type ItemEntrada = {
  descripcion: string; unidad_medida: string; cantidad: string;
  precio_unitario_ref: string; fuente_precio: "COTIZACION" | "COMPRA_ANTERIOR";
};
export type RequerimientoEntrada = {
  meta_codigo: string; objeto_contratacion: "BIEN" | "SERVICIO"; descripcion: string;
  items: ItemEntrada[]; fecha_necesidad: string; pac_item_referencia: string | null;
};
export type ResultadoRegistro = { requerimiento_id: number; codigo: string; estado_semaforo: string };
export type Etapa = {
  codigo: string; nombre: string; rol_a_cargo: string; cumplida: boolean; actual: boolean;
  fecha_hora: string | null; rol_registro: string | null; observacion: string | null;
};
export type Detalle = {
  requerimiento_id: number; codigo: string; unidad_organica: string; meta_codigo: string;
  meta_nombre: string; objeto_contratacion: string; descripcion: string; monto_estimado: string;
  fecha_necesidad: string; fecha_registro: string; estado_actual: string;
  responsable_actual: string; accion_pendiente: string;
  items: (ItemEntrada & { id_item: number; especificacion: string | null; subtotal: string })[];
  etapas: Etapa[];
  semaforo: {
    estado: "VERDE" | "AMBAR" | "ROJO"; motivo: string; fecha_hora: string; opciones_ajuste: string[];
    base_calculo: {
      pim: string | null; certificacion: string | null; compromiso_anual: string | null;
      columna_comparacion: "COMPROMISO" | "CERTIFICACION";
      saldo_disponible: string | null; monto_evaluado: string; fecha_corte: string | null;
      previsto_en_pac: boolean; pac_item_referencia: string | null;
    };
  };
  // Semáforo vigente (RI-20) y paso 2 (cambio 15 de la Práctica 7).
  semaforo_vigente: "VERDE" | "AMBAR_PENDIENTE" | "AMBAR_DENEGADO" | "ROJO";
  confirmado_por_presupuesto: boolean;
  plazo_entrega_dias: number | null;
  lugar_entrega: string | null;
  fecha_envio: string | null;
  puede_completar_paso_2: boolean;
};
export type Paso2Entrada = {
  items: { id_item: number; especificacion: string | null }[];
  plazo_entrega_dias: number | null;
  lugar_entrega: string | null;
};
export type Documentos = {
  documento_requerimiento_firmado: boolean; cuadro_necesidades: boolean; especificaciones_tecnicas_tdr: boolean;
};
export type ResultadoEnvio = { requerimiento_id: number; codigo: string; fecha_envio: string };

export class ErrorApi extends Error {
  constructor(
    mensaje: string, public estado: number,
    public errores: { campo: string; mensaje: string }[] = [],
    public datos: Record<string, unknown> = {},
  ) {
    super(mensaje);
  }
}

export type Rol = { codigo: "AU" | "GA" | "JL" | "JP" | "ADM"; nombre: string };
export type Unidad = { sigla: string | null; nombre: string };
export type UsuarioSesion = {
  id_usuario: number; nombre_usuario: string; nombres_apellidos: string; rol: Rol;
  unidad: Unidad | null; contrasena_temporal: boolean; reglas_contrasena: string[];
};
export type Usuario = {
  id_usuario: number; nombre_usuario: string; nombres_apellidos: string; rol: Rol;
  unidad: Unidad | null; estado: "ACTIVO" | "BAJA"; contrasena_temporal: boolean; bloqueado: boolean;
};
export type UsuarioEntrada = {
  nombre_usuario: string; nombres_apellidos: string; codigo_rol: Rol["codigo"]; unidad_sigla: string | null;
};
export type ContrasenaTemporal = { usuario: Usuario; contrasena_temporal: string };
export type Pendiente = {
  requerimiento_id: number; codigo: string; descripcion: string; situacion: string;
  motivo: string; desde: string; accion: string; destino: string;
};
export type Inicio = {
  fecha_corte_mef: string | null; fecha_corte_seace: string | null;
  tarjetas: { verde: number; ambar: number; rojo: number; observado: number; cuello_de_botella: number } | null;
  pendientes: Pendiente[]; pendientes_disponibles: boolean;
};

const MENSAJE_TEMPORAL = "Debe cambiar su contraseña temporal antes de continuar.";
let renovando: Promise<boolean> | null = null;

/** Renueva la sesión una sola vez aunque varias peticiones fallen al mismo tiempo. */
function renovarSesion(): Promise<boolean> {
  renovando ??= fetch(`${BASE}/auth/renovacion`, { method: "POST" })
    .then((r) => r.ok).catch(() => false)
    .finally(() => setTimeout(() => { renovando = null; }, 0));
  return renovando;
}

export function irAIngreso(motivo?: "temporal"): never {
  const volver = window.location.pathname + window.location.search;
  const parametros = new URLSearchParams();
  if (!volver.startsWith("/ingreso") && volver !== "/") parametros.set("volver", volver);
  if (motivo) parametros.set("motivo", motivo);
  window.location.href = `/ingreso${parametros.size ? `?${parametros}` : ""}`;
  throw new ErrorApi("Redirigiendo a Iniciar sesión…", 401);
}

async function pedir<T>(ruta: string, opciones?: RequestInit, reintento = true): Promise<T> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE}${ruta}`, {
      ...opciones, headers: { "Content-Type": "application/json", ...opciones?.headers },
    });
  } catch {
    throw new ErrorApi("No se pudo conectar con el sistema. Verifique su conexión e intente de nuevo.", 0);
  }
  const deAutenticacion = ruta.startsWith("/auth/");
  if (respuesta.status === 401 && !deAutenticacion) {
    if (reintento && await renovarSesion()) return pedir<T>(ruta, opciones, false);
    irAIngreso();
  }
  if (!respuesta.ok) {
    const problema = await respuesta.json().catch(() => ({}));
    if (respuesta.status === 403 && problema.detail === MENSAJE_TEMPORAL) irAIngreso("temporal");
    let mensaje: string = problema.detail ?? "Ocurrió un error inesperado.";
    if (respuesta.status >= 500 && !problema.codigo_referencia) {
      mensaje = "El sistema no está disponible en este momento. Intente de nuevo en unos segundos.";
    }
    throw new ErrorApi(mensaje, respuesta.status, problema.errores ?? [], problema);
  }
  if (respuesta.status === 204) return undefined as T;
  return respuesta.json() as Promise<T>;
}

const json = (method: string, cuerpo?: unknown): RequestInit =>
  ({ method, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });

export const auth = {
  ingresar: (nombre_usuario: string, contrasena: string) =>
    pedir<UsuarioSesion>("/auth/ingreso", json("POST", { nombre_usuario, contrasena })),
  yo: async (): Promise<UsuarioSesion | null> => {
    try {
      return await pedir<UsuarioSesion>("/auth/yo");
    } catch (e) {
      if ((e as ErrorApi).estado !== 401) throw e;
      return await renovarSesion() ? pedir<UsuarioSesion>("/auth/yo") : null;
    }
  },
  cambiarContrasena: (contrasena_actual: string, contrasena_nueva: string) =>
    pedir<void>("/auth/cambio-contrasena", json("POST", { contrasena_actual, contrasena_nueva })),
  salir: () => pedir<void>("/auth/salida", json("POST")),
};

export const usuarios = {
  catalogos: () => pedir<{ roles: Rol[]; unidades: Unidad[] }>("/usuarios/catalogos"),
  listar: (filtros: Record<string, string>) => {
    const q = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v));
    return pedir<Usuario[]>(`/usuarios${q.size ? `?${q}` : ""}`);
  },
  crear: (datos: UsuarioEntrada) => pedir<ContrasenaTemporal>("/usuarios", json("POST", datos)),
  modificar: (id: number, datos: Omit<UsuarioEntrada, "nombre_usuario">) =>
    pedir<Usuario>(`/usuarios/${id}`, json("PUT", datos)),
  restablecer: (id: number) => pedir<ContrasenaTemporal>(`/usuarios/${id}/restablecimiento`, json("POST")),
  darDeBaja: (id: number) => pedir<Usuario>(`/usuarios/${id}/baja`, json("POST")),
};

export const api = {
  inicio: () => pedir<Inicio>("/inicio"),
  metas: () => pedir<Meta[]>("/metas"),
  pac: () => pedir<PacItem[]>("/pac-items"),
  regla: () => pedir<ReglaVigente>("/regla-vigente"),
  registrar: (datos: RequerimientoEntrada) =>
    pedir<ResultadoRegistro>("/requerimientos", { method: "POST", body: JSON.stringify(datos) }),
  detalle: (id: number) => pedir<Detalle>(`/requerimientos/${id}`),
  guardarPaso2: (id: number, datos: Paso2Entrada) =>
    pedir<Detalle>(`/requerimientos/${id}/paso-2`, { method: "PUT", body: JSON.stringify(datos) }),
  enviar: (id: number, datos: Paso2Entrada & { documentos: Documentos }) =>
    pedir<ResultadoEnvio>(`/requerimientos/${id}/envio`, { method: "POST", body: JSON.stringify(datos) }),
};
