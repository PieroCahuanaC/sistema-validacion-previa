// P07. Historial de trazabilidad del expediente (CU-02, CU-10; RF-05 a RF-07; Tabla 8 de la
// Práctica 7). Solo lectura: muestra roles funcionales, nunca nombres de personas.
import { useEffect, useState } from "react";
import { api, ErrorApi, type Historial } from "../lib/api";
import { formatoFechaHora, formatoSoles } from "../lib/formato";
import { Aviso, horasTexto, parametro, secundario, Semaforo } from "./comunes";

export default function HistorialExpediente() {
  const id = Number(parametro("id"));
  const [historial, setHistorial] = useState<Historial | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) { setError("Indique el requerimiento que desea consultar."); return; }
    api.historial(id).then(setHistorial).catch((e: ErrorApi) => setError(e.message));
  }, [id]);

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!historial) return <p className="text-pizarra">Cargando el historial…</p>;
  const h = historial;

  return (
    <div className="max-w-4xl space-y-4">
      <section className="rounded border border-linea bg-superficie p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-bold">{h.codigo}</h2>
          <Semaforo vigente={h.semaforo_vigente} />
          <span className="rounded border border-linea px-2 py-0.5 text-xs font-semibold">{h.estado_actual}</span>
        </div>
        <p className="mt-1 text-sm">{h.descripcion}</p>
        <p className="mt-1 text-sm text-pizarra">Meta {h.meta_codigo} · Monto estimado {formatoSoles(h.monto_estimado)}</p>
        <p className="mt-2 text-sm">
          {h.cerrado ? <strong>Trámite cerrado.</strong> : <>Responsable actual: <strong>{h.responsable_actual}</strong>. Acción pendiente: {h.accion_pendiente}.</>}
        </p>
        <dl className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="rounded bg-fondo p-3"><dt className="text-xs text-pizarra">Tiempo hasta la certificación</dt>
            <dd className="cifra text-lg font-bold">{h.horas_hasta_certificacion === null ? "Aún no certificado" : horasTexto(h.horas_hasta_certificacion)}</dd></div>
          <div className="rounded bg-fondo p-3"><dt className="text-xs text-pizarra">Tiempo total hasta Orden emitida</dt>
            <dd className="cifra text-lg font-bold">{h.horas_totales === null ? (h.estado_actual === "Anulado" ? "Anulado" : "En curso") : horasTexto(h.horas_totales)}</dd></div>
        </dl>
      </section>

      <section aria-label="Línea de tiempo" className="rounded border border-linea bg-superficie p-4">
        <h2 className="mb-3 font-semibold">Línea de tiempo</h2>
        <ol className="relative space-y-4 border-l-2 border-linea pl-6">
          {h.registros.map((r, n) => (
            <li key={n} className="relative">
              <span aria-hidden="true" className={`absolute top-1 -left-[33px] h-4 w-4 rounded-full border-2 ${r.en_curso
                ? "border-accion bg-white" : r.estado_codigo === "ANULADO" ? "border-rojo bg-rojo" : "border-accion bg-accion"}`} />
              <p className="font-semibold">{r.estado}{r.en_curso && <span className="ml-2 text-xs font-normal text-accion">(etapa actual)</span>}</p>
              <p className="text-sm text-pizarra">{formatoFechaHora(r.fecha_hora)} · {r.rol}</p>
              {r.observacion && <p className="mt-1 rounded bg-fondo p-2 text-sm">Proveído u observación: {r.observacion}</p>}
              {r.horas_en_etapa !== null && (
                <p className="mt-1 text-xs">
                  {r.en_curso ? "Lleva" : "Duró"} {horasTexto(r.horas_en_etapa)}{r.plazo_horas ? ` · plazo ${horasTexto(r.plazo_horas)}` : ""}
                  {r.excedio_plazo && <span className="ml-2 rounded bg-rojo-suave px-1.5 py-0.5 font-semibold text-rojo">Excedió el plazo</span>}
                </p>
              )}
            </li>
          ))}
          {h.etapas_futuras.map((e) => (
            <li key={e.estado_codigo} className="relative text-pizarra/60">
              <span aria-hidden="true" className="absolute top-1 -left-[33px] h-4 w-4 rounded-full border-2 border-linea bg-white" />
              <p>{e.estado}</p><p className="text-xs">Etapa pendiente</p>
            </li>
          ))}
        </ol>
      </section>

      <div className="flex justify-end gap-3">
        <button type="button" onClick={() => history.back()} className={secundario}>Volver</button>
        <a href={`/requerimientos/detalle?id=${h.requerimiento_id}`} className={secundario}>Ver detalle</a>
      </div>
    </div>
  );
}
