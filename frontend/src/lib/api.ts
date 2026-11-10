// Cliente de la API REST /api/v1 (contrato de la Práctica 5). Los errores llegan en formato
// Problem Details; aquí se convierten en un mensaje que la pantalla puede mostrar.
const BASE = (import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

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
  constructor(mensaje: string, public estado: number, public errores: { campo: string; mensaje: string }[] = []) {
    super(mensaje);
  }
}

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE}/api/v1${ruta}`, {
      ...opciones, headers: { "Content-Type": "application/json", ...opciones?.headers },
    });
  } catch {
    throw new ErrorApi("No se pudo conectar con el sistema. Verifique su conexión e intente de nuevo.", 0);
  }
  if (!respuesta.ok) {
    const problema = await respuesta.json().catch(() => ({}));
    throw new ErrorApi(problema.detail ?? "Ocurrió un error inesperado.", respuesta.status, problema.errores ?? []);
  }
  return respuesta.json() as Promise<T>;
}

export const api = {
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
