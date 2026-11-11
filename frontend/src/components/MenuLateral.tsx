// Menú lateral de la plantilla: solo las opciones del rol autenticado (RF-10, RNF-03, H8).
import { useEffect, useState } from "react";
import type { UsuarioSesion } from "../lib/api";
import { MENU_POR_ROL, sesionActual } from "../lib/sesion";

export default function MenuLateral({ activo }: { activo: string }) {
  const [usuario, setUsuario] = useState<UsuarioSesion | null>(null);
  useEffect(() => { sesionActual().then(setUsuario).catch(() => undefined); }, []);

  if (!usuario) {
    return <ul className="space-y-2" aria-busy="true">{[0, 1, 2].map((i) =>
      <li key={i} className="h-9 animate-pulse rounded bg-fondo" />)}</ul>;
  }
  return (
    <ul className="space-y-1 text-sm">
      {MENU_POR_ROL[usuario.rol.codigo].map((op) => (
        <li key={op.id}>
          {op.href ? (
            <a href={op.href} aria-current={op.id === activo ? "page" : undefined}
              className={`block rounded px-3 py-2 ${op.id === activo ? "bg-accion font-semibold text-white" : "hover:bg-fondo"}`}>
              {op.texto}</a>
          ) : (
            <span className="block cursor-not-allowed rounded px-3 py-2 text-pizarra/70" aria-disabled="true"
              title="Esta pantalla se habilita en un siguiente incremento">
              {op.texto} <span className="text-xs">(próximamente)</span></span>
          )}
        </li>
      ))}
    </ul>
  );
}
