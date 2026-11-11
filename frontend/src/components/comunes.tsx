// Piezas comunes a las pantallas del trámite: la misma ventana de confirmación para toda
// acción irreversible, el mismo indicador de semáforo con color y texto, y el mismo campo de
// observación con contador (H4, consistencia y estándares; Práctica 7).
import { useEffect, useRef, type ReactNode } from "react";

export const campo = "w-full rounded border border-linea bg-white px-3 py-2";
export const etiqueta = "mb-1 block text-sm font-semibold";
export const principal = "rounded bg-accion px-4 py-2 font-semibold text-white hover:bg-accion-hover disabled:cursor-not-allowed disabled:opacity-40";
export const secundario = "rounded border border-linea bg-white px-4 py-2 font-semibold hover:bg-fondo disabled:cursor-not-allowed disabled:opacity-40";
export const peligro = "rounded bg-rojo px-4 py-2 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40";

const SEMAFORO: Record<string, { texto: string; clase: string }> = {
  VERDE: { texto: "Verde", clase: "border-verde bg-verde-suave text-verde" },
  AMBAR: { texto: "Ámbar", clase: "border-ambar bg-ambar-suave text-ambar" },
  AMBAR_PENDIENTE: { texto: "Ámbar · Pendiente de Presupuesto", clase: "border-ambar bg-ambar-suave text-ambar" },
  AMBAR_DENEGADO: { texto: "Ámbar · Denegado", clase: "border-ambar bg-ambar-suave text-ambar" },
  ROJO: { texto: "Rojo", clase: "border-rojo bg-rojo-suave text-rojo" },
};

/** Semáforo siempre con color y texto, nunca solo color (WCAG 1.4.1). */
export function Semaforo({ vigente, confirmado }: { vigente: string; confirmado?: boolean }) {
  const s = SEMAFORO[vigente] ?? { texto: vigente, clase: "border-linea" };
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${s.clase}`}>
      {confirmado ? "Verde · Confirmado por Presupuesto" : s.texto}
    </span>
  );
}

export const MOTIVO_CORTO: Record<string, string> = {
  DISPONIBLE: "Saldo disponible",
  PRESUPUESTO_INSUFICIENTE: "Presupuesto insuficiente",
  SIN_DATOS_META: "Meta sin datos",
  DATO_DESACTUALIZADO: "Dato desactualizado",
  NO_PREVISTO_PAC: "No previsto en el PAC",
};

export function horasTexto(horas: number | null | undefined): string {
  if (horas === null || horas === undefined) return "—";
  const dias = Math.floor(horas / 24);
  const resto = Math.floor(horas % 24);
  return dias ? `${dias} d ${resto} h` : `${resto} h`;
}

export function AreaObservacion({ id, texto, valor, onChange, obligatoria, ayuda }: {
  id: string; texto: string; valor: string; onChange: (v: string) => void; obligatoria?: boolean; ayuda?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className={etiqueta}>{texto} {obligatoria && <span aria-hidden="true">*</span>}</label>
      <textarea id={id} rows={3} maxLength={500} value={valor} onChange={(e) => onChange(e.target.value)}
        className={campo} aria-describedby={`${id}-ayuda`} />
      <p id={`${id}-ayuda`} className="mt-1 flex justify-between text-xs text-pizarra">
        <span>{ayuda}</span><span className="cifra">{valor.length}/500</span>
      </p>
    </div>
  );
}

/** Ventana de confirmación única para toda acción que cambia el trámite (H3, H4). */
export function Confirmacion({ titulo, children, textoAccion, onConfirmar, onCancelar, ocupado, tipo = "principal" }: {
  titulo: string; children: ReactNode; textoAccion: string; onConfirmar: () => void; onCancelar: () => void;
  ocupado?: boolean; tipo?: "principal" | "peligro";
}) {
  const cancelar = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelar.current?.focus();
    const tecla = (e: KeyboardEvent) => { if (e.key === "Escape" && !ocupado) onCancelar(); };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [ocupado, onCancelar]);
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-tinta/50 p-4">
      <div role="alertdialog" aria-modal="true" aria-labelledby="titulo-confirmacion" className="w-full max-w-md rounded bg-superficie p-5 shadow-lg">
        <h2 id="titulo-confirmacion" className="text-lg font-bold">{titulo}</h2>
        <div className="mt-3 space-y-2 text-sm">{children}</div>
        <div className="mt-5 flex justify-end gap-3">
          <button ref={cancelar} type="button" className={secundario} onClick={onCancelar} disabled={ocupado}>Cancelar</button>
          <button type="button" className={tipo === "peligro" ? peligro : principal} onClick={onConfirmar} disabled={ocupado}>
            {ocupado ? "Registrando…" : textoAccion}</button>
        </div>
      </div>
    </div>
  );
}

export function Aviso({ tipo, children }: { tipo: "ok" | "error" | "info" | "atencion"; children: ReactNode }) {
  const estilo = {
    ok: "border-verde bg-verde-suave", error: "border-rojo bg-rojo-suave",
    info: "border-accion bg-superficie", atencion: "border-ambar bg-ambar-suave",
  }[tipo];
  return <div role={tipo === "error" ? "alert" : "status"} className={`rounded border-l-4 p-3 text-sm ${estilo}`}>{children}</div>;
}

export function parametro(nombre: string): string | null {
  return typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get(nombre);
}
