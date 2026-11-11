// P17. Mis requerimientos (CU-04, RF-03, RF-06; Figura 18 y Tabla 18 de la Práctica 7).
// Lista de trabajo del Área Usuaria con una acción por fila; las tarjetas de la P02 la abren
// ya filtrada (H7). Incluye los requerimientos cerrados.
import { useEffect, useState } from "react";
import { api, ErrorApi, type MiRequerimiento } from "../lib/api";
import { formatoFecha, formatoSoles } from "../lib/formato";
import { Aviso, campo, etiqueta, parametro, Semaforo } from "./comunes";

const ESTADOS = [
  ["REGISTRADO", "Registrado"], ["APROBADO", "Aprobado"], ["DOCUMENTACION_VALIDADA", "Documentación validada"],
  ["CUADRO_REGISTRADO", "Cuadro comparativo registrado"], ["CERTIFICADO", "Certificado"],
  ["ORDEN_EMITIDA", "Orden emitida"], ["OBSERVADO", "Observado"], ["ANULADO", "Anulado"],
];

export default function MisRequerimientos() {
  const [filtros, setFiltros] = useState({
    semaforo: parametro("semaforo") ?? "", estado: parametro("estado") ?? "", buscar: "",
    cuello_de_botella: parametro("cuello_de_botella") === "true" ? "true" : "",
  });
  const [filas, setFilas] = useState<MiRequerimiento[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const espera = setTimeout(() => {
      api.misRequerimientos(filtros).then(setFilas).catch((e: ErrorApi) => setError(e.message));
    }, 250);
    return () => clearTimeout(espera);
  }, [filtros]);

  return (
    <div className="space-y-4">
      {error && <Aviso tipo="error">{error}</Aviso>}
      <div className="flex flex-wrap items-end gap-3 rounded border border-linea bg-superficie p-3">
        <div>
          <label htmlFor="f-semaforo" className={etiqueta}>Semáforo</label>
          <select id="f-semaforo" className={campo} value={filtros.semaforo} onChange={(e) => setFiltros({ ...filtros, semaforo: e.target.value })}>
            <option value="">Todos</option><option value="VERDE">Verde</option><option value="AMBAR">Ámbar</option><option value="ROJO">Rojo</option>
          </select>
        </div>
        <div>
          <label htmlFor="f-estado" className={etiqueta}>Estado</label>
          <select id="f-estado" className={campo} value={filtros.estado} onChange={(e) => setFiltros({ ...filtros, estado: e.target.value })}>
            <option value="">Todos</option>
            {ESTADOS.map(([codigo, nombre]) => <option key={codigo} value={codigo}>{nombre}</option>)}
          </select>
        </div>
        <div className="min-w-48 flex-1">
          <label htmlFor="f-buscar" className={etiqueta}>Buscar por código</label>
          <input id="f-buscar" type="search" maxLength={15} placeholder="REQ-2026-…" className={campo}
            value={filtros.buscar} onChange={(e) => setFiltros({ ...filtros, buscar: e.target.value })} />
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={filtros.cuello_de_botella === "true"}
            onChange={(e) => setFiltros({ ...filtros, cuello_de_botella: e.target.checked ? "true" : "" })} />
          Con cuello de botella
        </label>
        <a href="/requerimientos/nuevo" className="rounded bg-accion px-4 py-2 font-semibold text-white hover:bg-accion-hover">Registrar requerimiento</a>
      </div>

      {filas === null ? <p className="text-pizarra">Cargando…</p> : filas.length === 0 ? (
        <p className="rounded border border-linea bg-superficie p-4 text-pizarra">No hay requerimientos con esos filtros.</p>
      ) : (
        <div className="overflow-x-auto rounded border border-linea bg-superficie">
          <table className="w-full text-left text-sm">
            <thead className="bg-fondo text-pizarra">
              <tr>
                <th scope="col" className="px-3 py-2">Código</th><th scope="col" className="px-3 py-2">Descripción</th>
                <th scope="col" className="px-3 py-2">Meta</th><th scope="col" className="px-3 py-2 text-right">Monto (S/)</th>
                <th scope="col" className="px-3 py-2">Semáforo vigente</th><th scope="col" className="px-3 py-2">Estado actual</th>
                <th scope="col" className="px-3 py-2">Fecha de necesidad</th><th scope="col" className="px-3 py-2"><span className="sr-only">Acción</span></th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.requerimiento_id} className="border-t border-linea">
                  <td className="px-3 py-2 font-semibold whitespace-nowrap">{f.codigo}</td>
                  <td className="max-w-xs px-3 py-2">{f.descripcion}</td>
                  <td className="px-3 py-2">{f.meta_codigo}</td>
                  <td className="cifra px-3 py-2 text-right">{formatoSoles(f.monto_estimado)}</td>
                  <td className="px-3 py-2"><Semaforo vigente={f.semaforo_vigente} /></td>
                  <td className="px-3 py-2">{f.estado_actual}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatoFecha(f.fecha_necesidad)}</td>
                  <td className="px-3 py-2 text-right">
                    <a href={f.destino} className={`inline-block rounded px-3 py-1.5 font-semibold whitespace-nowrap ${f.accion
                      ? "bg-accion text-white hover:bg-accion-hover" : "border border-linea hover:bg-fondo"}`}>{f.accion ?? "Ver"}</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
