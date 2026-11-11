// Parte derecha de la barra superior: campana de pendientes, rol y unidad del usuario y
// Cerrar sesión (Tabla 3 de la Práctica 7). La campana no se muestra al Administrador.
import { useEffect, useState } from "react";
import { auth, type UsuarioSesion } from "../lib/api";
import { inicioActual, sesionActual } from "../lib/sesion";

export default function BarraUsuario() {
  const [usuario, setUsuario] = useState<UsuarioSesion | null>(null);
  const [pendientes, setPendientes] = useState<number | null>(null);
  const [saliendo, setSaliendo] = useState(false);

  useEffect(() => {
    sesionActual().then((u) => {
      setUsuario(u);
      if (u.rol.codigo !== "ADM") {
        inicioActual().then((i) => setPendientes(i.pendientes_disponibles ? i.pendientes.length : null))
          .catch(() => undefined);
      }
    }).catch(() => undefined);
  }, []);

  async function salir() {
    setSaliendo(true);
    try { await auth.salir(); } catch { /* aunque falle la red, se vuelve a la P01 */ }
    window.location.href = "/ingreso?salida=1";
  }

  if (!usuario) return <span className="text-sm text-white/70">Cargando sesión…</span>;
  const rol = usuario.unidad?.sigla ? `${usuario.rol.nombre} · ${usuario.unidad.sigla}` : usuario.rol.nombre;
  return (
    <span className="flex items-center gap-4 text-sm">
      {usuario.rol.codigo !== "ADM" && (
        <a href="/inicio#pendientes" className="relative rounded px-2 py-1 hover:bg-white/10"
          aria-label={pendientes === null ? "Pendientes de su acción" : `Pendientes de su acción: ${pendientes}`}
          title="Pendientes de su acción">
          <span aria-hidden="true">🔔</span>
          {pendientes !== null && pendientes > 0 && (
            <span className="cifra absolute -top-1 -right-1 min-w-5 rounded-full bg-rojo px-1 text-center text-xs font-bold">
              {pendientes}</span>
          )}
        </a>
      )}
      <span className="text-right leading-tight">
        <span className="block font-semibold">{rol}</span>
        <span className="block text-xs text-white/75">{usuario.nombres_apellidos}</span>
      </span>
      <button type="button" onClick={salir} disabled={saliendo}
        className="rounded border border-white/40 px-3 py-1 hover:bg-white/10 disabled:opacity-60">
        {saliendo ? "Cerrando…" : "Cerrar sesión"}</button>
    </span>
  );
}
