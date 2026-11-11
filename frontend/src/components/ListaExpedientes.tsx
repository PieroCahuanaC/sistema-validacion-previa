// Lista de expedientes por estado, común a las pantallas de Logística (P09, P10, P13) y de
// Presupuesto (P12): misma tabla, misma columna de plazo y la fila elegida abre el panel de la
// derecha (H4, consistencia; H7, la P02 la abre ya con el requerimiento seleccionado).
import { useCallback, useEffect, useState } from "react";
import { api, ErrorApi, type Expediente } from "../lib/api";
import { formatoSoles } from "../lib/formato";
import { horasTexto, parametro, Semaforo } from "./comunes";

export function useExpedientes(estado: string) {
  const [filas, setFilas] = useState<Expediente[] | null>(null);
  const [elegido, setElegido] = useState<number | null>(Number(parametro("id")) || null);
  const [error, setError] = useState("");
  const cargar = useCallback(() => api.expedientes(estado).then((f) => {
    setFilas(f);
    setElegido((actual) => (actual && f.some((x) => x.requerimiento_id === actual) ? actual : f[0]?.requerimiento_id ?? null));
  }).catch((e: ErrorApi) => setError(e.message)), [estado]);
  useEffect(() => { cargar(); }, [cargar]);
  const fila = filas?.find((f) => f.requerimiento_id === elegido) ?? null;
  return { filas, fila, elegido, setElegido, cargar, error };
}

export function TablaExpedientes({ titulo, filas, elegido, onElegir, vacio, precio }: {
  titulo: string; filas: Expediente[] | null; elegido: number | null; onElegir: (id: number) => void;
  vacio: string; precio?: boolean;
}) {
  if (filas === null) return <p className="text-pizarra">Cargando…</p>;
  if (filas.length === 0) return <p className="rounded border border-linea bg-superficie p-4 text-pizarra">{vacio}</p>;
  return (
    <section className="overflow-x-auto rounded border border-linea bg-superficie">
      <table className="w-full text-left text-sm">
        <caption className="p-3 text-left font-semibold">{titulo} ({filas.length})</caption>
        <thead className="bg-fondo text-pizarra">
          <tr>
            <th scope="col" className="px-3 py-2">Código</th>
            <th scope="col" className="hidden px-3 py-2 2xl:table-cell">Unidad / meta</th>
            <th scope="col" className="px-3 py-2 text-right">{precio ? "Precio de referencia" : "Monto"}</th>
            <th scope="col" className="px-3 py-2">Semáforo</th>
            <th scope="col" className="px-3 py-2">En la etapa / plazo</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.requerimiento_id} onClick={() => onElegir(f.requerimiento_id)}
              className={`cursor-pointer border-t border-linea align-top ${f.requerimiento_id === elegido ? "bg-fondo" : "hover:bg-fondo/60"}`}>
              <td className="px-3 py-2">
                <button type="button" className="font-semibold whitespace-nowrap hover:underline" aria-pressed={f.requerimiento_id === elegido}
                  onClick={() => onElegir(f.requerimiento_id)}>{f.codigo}</button>
                <span className="block max-w-56 text-xs text-pizarra">{f.descripcion}</span>
                <span className="block text-xs text-pizarra 2xl:hidden">{f.unidad_sigla} · Meta {f.meta_codigo}</span>
                {f.nota && <span className={`mt-1 block text-xs font-semibold ${f.devuelto ? "text-rojo" : "text-ambar"}`}>{f.nota}</span>}
              </td>
              <td className="hidden px-3 py-2 2xl:table-cell">{f.unidad_sigla} · {f.meta_codigo}</td>
              <td className="cifra px-3 py-2 text-right">{formatoSoles(precio ? f.precio_referencia : f.monto_estimado)}</td>
              <td className="px-3 py-2"><Semaforo vigente={f.semaforo_vigente} confirmado={f.confirmado_por_presupuesto} /></td>
              <td className="px-3 py-2">
                <span className="whitespace-nowrap">{horasTexto(f.horas_en_etapa)}</span> / <span className="whitespace-nowrap">{horasTexto(f.plazo_horas)}</span>
                {f.excedido && <span className="ml-2 rounded bg-rojo-suave px-1.5 py-0.5 text-xs font-semibold text-rojo">Excedido</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function EnlacesExpediente({ id }: { id: number }) {
  return (
    <p className="text-sm">
      <a className="font-semibold text-accion hover:underline" href={`/requerimientos/detalle?id=${id}`}>Ver detalle completo</a>
      {" · "}
      <a className="font-semibold text-accion hover:underline" href={`/requerimientos/historial?id=${id}`}>Ver historial</a>
    </p>
  );
}
