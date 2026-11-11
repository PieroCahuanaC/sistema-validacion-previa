// Sesión del usuario para la plantilla común: una sola consulta a /auth/yo por página, que
// comparten la barra superior y el menú lateral (P02, Tabla 3 de la Práctica 7).
import { api, auth, irAIngreso, type Inicio, type Rol, type UsuarioSesion } from "./api";

let consulta: Promise<UsuarioSesion> | null = null;
let inicio: Promise<Inicio> | null = null;

/** Usuario con sesión vigente; si no la hay o su contraseña es temporal, va a la P01. */
export function sesionActual(): Promise<UsuarioSesion> {
  consulta ??= auth.yo().then((usuario) => {
    if (!usuario) irAIngreso();
    if (usuario.contrasena_temporal) irAIngreso("temporal");
    return usuario;
  });
  return consulta;
}

/** Datos de la P02; la campana y la pantalla Inicio comparten la misma consulta. */
export function inicioActual(): Promise<Inicio> {
  inicio ??= sesionActual().then(() => api.inicio());
  return inicio;
}

export type OpcionMenu = { id: string; texto: string; href: string | null };

// Menú lateral por rol (RF-10, RNF-03; Figura 2 y Tabla 19 de la Práctica 7). Inicio va siempre
// primero (H4). Las opciones cuya pantalla llega en un incremento posterior se muestran
// deshabilitadas para que cada rol reconozca desde ya dónde estará su trabajo.
export const MENU_POR_ROL: Record<Rol["codigo"], OpcionMenu[]> = {
  AU: [
    { id: "inicio", texto: "Inicio", href: "/inicio" },
    { id: "registrar", texto: "Registrar requerimiento", href: "/requerimientos/nuevo" },
    { id: "mis", texto: "Mis requerimientos", href: "/requerimientos" },
    { id: "tablero", texto: "Tablero", href: null },
  ],
  GA: [
    { id: "inicio", texto: "Inicio", href: "/inicio" },
    { id: "bandeja", texto: "Bandeja de aprobación", href: "/bandeja" },
    { id: "tablero", texto: "Tablero", href: null },
  ],
  JL: [
    { id: "inicio", texto: "Inicio", href: "/inicio" },
    { id: "validacion", texto: "Validación documental", href: null },
    { id: "cuadro", texto: "Cuadro comparativo", href: null },
    { id: "orden", texto: "Registrar orden y compromiso", href: null },
    { id: "tablero", texto: "Tablero", href: null },
  ],
  JP: [
    { id: "inicio", texto: "Inicio", href: "/inicio" },
    { id: "alertas", texto: "Panel de alertas", href: "/alertas" },
    { id: "certificacion", texto: "Registrar certificación", href: null },
    { id: "reglas", texto: "Configurar reglas del semáforo", href: null },
    { id: "base", texto: "Base presupuestal", href: null },
    { id: "tablero", texto: "Tablero", href: null },
  ],
  ADM: [
    { id: "inicio", texto: "Inicio", href: "/inicio" },
    { id: "usuarios", texto: "Gestionar usuarios", href: "/usuarios" },
  ],
};

/** Ruta de ingreso segura: solo rutas internas, nunca otro sitio (redirección abierta). */
export function rutaInterna(valor: string | null): string {
  if (!valor || !valor.startsWith("/") || valor.startsWith("//") || valor.startsWith("/\\")) return "/inicio";
  return valor.startsWith("/ingreso") ? "/inicio" : valor;
}
