// P06. Tablero de visibilidad (CU-02; RF-06 a RF-08; Figura 7 y Tabla 7 de la Práctica 7).
// Seguimiento de tiempos y cuellos de botella: a diferencia de la P17, no es una lista de
// trabajo; cada fila lleva a su historial (P07). El Área Usuaria ve solo su unidad.
import { useEffect, useState } from "react";
import { api, ErrorApi, type FilaTablero, type Tablero as DatosTablero } from "../lib/api";
import { formatoFecha, formatoSoles } from "../lib/formato";
import { sesionActual } from "../lib/sesion";
import { Aviso, campo, etiqueta, horasTexto, parametro, secundario, Semaforo } from "./comunes";

const ESTADOS = [
  ["REGISTRADO", "Registrado"], ["APROBADO", "Aprobado"], ["DOCUMENTACION_VALIDADA", "Documentación validada"],
  ["CUADRO_REGISTRADO", "Cuadro comparativo registrado"], ["CERTIFICADO", "Certificado"],
  ["ORDEN_EMITIDA", "Orden emitida"], ["OBSERVADO", "Observado"], ["ANULADO", "Anulado"],
];
const SIN_FILTROS = { meta: "", semaforo: "", estado: "", buscar: "", cuello_de_botella: "" };
type Filtros = typeof SIN_FILTROS;
type Orden = "meta" | "codigo" | "objeto" | "unidad" | "monto" | "saldo" | "fecha_necesidad" | "tiempo";

function Tarjeta({ titulo, valor, color, activa, onClick }: {
  titulo: string; valor: number; color?: string; activa: boolean; onClick: () => void;
}) {
  // Cada tarjeta filtra la tabla (H7); la activa queda marcada.
  return (
    <button type="button" onClick={onClick} aria-pressed={activa}
      className={`rounded border bg-superficie p-3 text-left hover:bg-fondo ${color ? `border-l-8 ${color}` : ""} ${activa ? "border-accion ring-2 ring-accion" : "border-linea"}`}>
      <span className="block text-sm text-pizarra">{titulo}</span>
      <span className="cifra mt-1 block text-2xl font-bold">{valor}</span>
    </button>
  );
}

function Encabezado({ texto, campo: clave, orden, descendente, onOrdenar, className = "" }: {
  texto: string; campo: Orden; orden: Orden; descendente: boolean; onOrdenar: (c: Orden) => void; className?: string;
}) {
  const activo = orden === clave;
  // Todas las columnas ordenables usan el mismo indicador (H4).
  return (
    <th scope="col" className={`px-2 py-2 ${className}`} aria-sort={activo ? (descendente ? "descending" : "ascending") : "none"}>
      <button type="button" className="inline-flex items-center gap-1 font-semibold whitespace-nowrap hover:text-tinta" onClick={() => onOrdenar(clave)}>
        {texto}<span aria-hidden="true" className="text-xs">{activo ? (descendente ? "▼" : "▲") : "↕"}</span>
      </button>
    </th>
  );
}

function Fila({ f, areaUsuaria, verUnidad }: { f: FilaTablero; areaUsuaria: boolean; verUnidad: boolean }) {
  const resaltada = f.cuello_de_botella ? "bg-rojo-suave/60" : f.cerrado ? "text-pizarra" : "";
  return (
    <tr className={`border-t border-linea ${resaltada}`}>
      <td className="px-2 py-2 font-semibold whitespace-nowrap">
        {areaUsuaria ? <a className="text-accion hover:underline" href={`/requerimientos/detalle?id=${f.requerimiento_id}`}>{f.codigo}</a> : f.codigo}
        <span className="block max-w-48 truncate text-xs font-normal text-pizarra" title={f.descripcion}>{f.descripcion}</span>
      </td>
      <td className="hidden px-2 py-2 2xl:table-cell">{f.objeto_contratacion === "BIEN" ? "Bien" : "Servicio"}</td>
      {verUnidad && <td className="px-2 py-2">{f.unidad_sigla}</td>}
      <td className="px-2 py-2" title={f.meta_nombre}>{f.meta_codigo}</td>
      <td className="cifra px-2 py-2 text-right">{formatoSoles(f.monto_estimado)}</td>
      <td className="cifra hidden px-2 py-2 text-right xl:table-cell">{f.saldo_disponible === null ? "Sin datos" : formatoSoles(f.saldo_disponible)}</td>
      <td className="hidden px-2 py-2 whitespace-nowrap 2xl:table-cell">{formatoFecha(f.fecha_necesidad)}</td>
      <td className="px-2 py-2"><Semaforo vigente={f.semaforo_vigente} /></td>
      <td className="px-2 py-2">
        {f.estado_actual}
        {f.cuello_de_botella && <span className="mt-1 block w-fit rounded border border-rojo bg-superficie px-1.5 text-xs font-semibold text-rojo">Cuello de botella</span>}
      </td>
      <td className="px-2 py-2 text-sm whitespace-nowrap">
        {f.cerrado ? "—" : f.horas_en_etapa === null
          ? <span className="text-pizarra">{f.estado_codigo === "REGISTRADO" ? "Sin enviar" : "—"}</span>
          : <>{horasTexto(f.horas_en_etapa)}<span className="block text-xs text-pizarra">de {f.plazo_horas ? horasTexto(f.plazo_horas) : "—"}</span></>}
      </td>
      <td className="px-2 py-2 text-right">
        <a className="font-semibold whitespace-nowrap text-accion hover:underline" href={`/requerimientos/historial?id=${f.requerimiento_id}`}>Ver</a>
      </td>
    </tr>
  );
}

export default function Tablero() {
  const [rol, setRol] = useState<string | null>(null);
  const [filtros, setFiltros] = useState<Filtros>({
    ...SIN_FILTROS, semaforo: parametro("semaforo") ?? "", estado: parametro("estado") ?? "",
    meta: parametro("meta") ?? "", cuello_de_botella: parametro("cuello_de_botella") === "true" ? "true" : "",
  });
  const [orden, setOrden] = useState<{ orden: Orden; descendente: boolean }>({ orden: "meta", descendente: false });
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState<DatosTablero | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { sesionActual().then((u) => setRol(u.rol.codigo)).catch(() => undefined); }, []);
  useEffect(() => {
    const espera = setTimeout(() => {
      api.tablero({ ...filtros, orden: orden.orden, descendente: orden.descendente ? "true" : "", pagina: String(pagina) })
        .then((d) => { setDatos(d); setError(""); }).catch((e: ErrorApi) => setError(e.message));
    }, 250);
    return () => clearTimeout(espera);
  }, [filtros, orden, pagina]);

  const cambiar = (nuevos: Partial<Filtros>) => { setFiltros({ ...filtros, ...nuevos }); setPagina(1); };
  const ordenar = (campoOrden: Orden) => {
    setOrden(orden.orden === campoOrden ? { orden: campoOrden, descendente: !orden.descendente } : { orden: campoOrden, descendente: false });
    setPagina(1);
  };
  const areaUsuaria = rol === "AU";
  const hayFiltros = Object.values(filtros).some(Boolean);
  const t = datos?.tarjetas;
  const porColor = (semaforo: string) => !filtros.estado && !filtros.cuello_de_botella && filtros.semaforo === semaforo;

  return (
    <div className="space-y-4">
      {error && <Aviso tipo="error">{error}</Aviso>}
      {datos && (
        <div role="status" className="rounded border-l-4 border-accion bg-superficie p-3 text-sm">
          Datos presupuestales al <strong>{formatoFecha(datos.fecha_corte_mef)}</strong> (Consulta Amigable del MEF).
          El saldo presupuestal disponible es crédito presupuestario aún no comprometido, no dinero en caja.
          {datos.unidad && <> Unidad orgánica: <strong>{datos.unidad}</strong>.</>}
        </div>
      )}

      {t && (
        <section aria-label="Resumen de requerimientos en trámite" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Tarjeta titulo="En trámite" valor={t.en_tramite} activa={!hayFiltros} onClick={() => cambiar(SIN_FILTROS)} />
          <Tarjeta titulo="Verde" valor={t.verde} color="border-l-verde" activa={porColor("VERDE")} onClick={() => cambiar({ ...SIN_FILTROS, semaforo: "VERDE" })} />
          <Tarjeta titulo="Ámbar" valor={t.ambar} color="border-l-ambar" activa={porColor("AMBAR")} onClick={() => cambiar({ ...SIN_FILTROS, semaforo: "AMBAR" })} />
          <Tarjeta titulo="Rojo" valor={t.rojo} color="border-l-rojo" activa={porColor("ROJO")} onClick={() => cambiar({ ...SIN_FILTROS, semaforo: "ROJO" })} />
          <Tarjeta titulo="Observados" valor={t.observado} activa={filtros.estado === "OBSERVADO"} onClick={() => cambiar({ ...SIN_FILTROS, estado: "OBSERVADO" })} />
          <Tarjeta titulo="Con cuello de botella" valor={t.cuello_de_botella} activa={filtros.cuello_de_botella === "true"} onClick={() => cambiar({ ...SIN_FILTROS, cuello_de_botella: "true" })} />
        </section>
      )}

      <div className="flex flex-wrap items-end gap-3 rounded border border-linea bg-superficie p-3">
        <div>
          <label htmlFor="f-meta" className={etiqueta}>Meta</label>
          <select id="f-meta" className={campo} value={filtros.meta} onChange={(e) => cambiar({ meta: e.target.value })}>
            <option value="">Todas</option>
            {datos?.metas.map((m) => <option key={m.codigo} value={m.codigo}>{m.codigo} · {m.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-semaforo" className={etiqueta}>Semáforo</label>
          <select id="f-semaforo" className={campo} value={filtros.semaforo} onChange={(e) => cambiar({ semaforo: e.target.value })}>
            <option value="">Todos</option><option value="VERDE">Verde</option><option value="AMBAR">Ámbar</option><option value="ROJO">Rojo</option>
          </select>
        </div>
        <div>
          <label htmlFor="f-estado" className={etiqueta}>Estado</label>
          <select id="f-estado" className={campo} value={filtros.estado} onChange={(e) => cambiar({ estado: e.target.value })}>
            <option value="">Todos</option>
            {ESTADOS.map(([codigo, nombre]) => <option key={codigo} value={codigo}>{nombre}</option>)}
          </select>
        </div>
        <div className="min-w-44 flex-1">
          <label htmlFor="f-buscar" className={etiqueta}>Buscar por código</label>
          <input id="f-buscar" type="search" maxLength={15} placeholder="REQ-2026-…" className={campo}
            value={filtros.buscar} onChange={(e) => cambiar({ buscar: e.target.value })} />
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={filtros.cuello_de_botella === "true"}
            onChange={(e) => cambiar({ cuello_de_botella: e.target.checked ? "true" : "" })} />
          Solo con cuello de botella
        </label>
        <button type="button" className={secundario} disabled={!hayFiltros} onClick={() => cambiar(SIN_FILTROS)}>Limpiar filtros</button>
      </div>

      {datos === null ? <p className="text-pizarra">Cargando…</p> : datos.filas.length === 0 ? (
        <p className="rounded border border-linea bg-superficie p-4 text-pizarra">No hay requerimientos con esos filtros.</p>
      ) : (
        <>
          <div className="overflow-x-auto rounded border border-linea bg-superficie">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Requerimientos con su semáforo, estado y tiempo en la etapa</caption>
              <thead className="bg-fondo text-pizarra">
                <tr>
                  <Encabezado texto="Código" campo="codigo" {...orden} onOrdenar={ordenar} />
                  <Encabezado texto="Objeto" campo="objeto" {...orden} onOrdenar={ordenar} className="hidden 2xl:table-cell" />
                  {!areaUsuaria && <Encabezado texto="Unidad" campo="unidad" {...orden} onOrdenar={ordenar} />}
                  <Encabezado texto="Meta" campo="meta" {...orden} onOrdenar={ordenar} />
                  <Encabezado texto="Monto (S/)" campo="monto" {...orden} onOrdenar={ordenar} className="text-right" />
                  <Encabezado texto="Saldo disponible (S/)" campo="saldo" {...orden} onOrdenar={ordenar} className="hidden text-right xl:table-cell" />
                  <Encabezado texto="Fecha de necesidad" campo="fecha_necesidad" {...orden} onOrdenar={ordenar} className="hidden 2xl:table-cell" />
                  <th scope="col" className="px-2 py-2">Semáforo vigente</th>
                  <th scope="col" className="px-2 py-2">Estado actual</th>
                  <Encabezado texto="Etapa / plazo" campo="tiempo" {...orden} onOrdenar={ordenar} />
                  <th scope="col" className="px-2 py-2"><span className="sr-only">Historial</span></th>
                </tr>
              </thead>
              <tbody>
                {datos.filas.map((f) => <Fila key={f.requerimiento_id} f={f} areaUsuaria={areaUsuaria} verUnidad={!areaUsuaria} />)}
              </tbody>
            </table>
          </div>
          <nav aria-label="Paginación" className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <p className="text-pizarra">
              {datos.total_filas} requerimiento(s) · página {datos.pagina} de {datos.paginas}
              {t && t.cerrados > 0 && <> · {t.cerrados} trámite(s) cerrado(s) en total</>}
            </p>
            <div className="flex gap-2">
              <button type="button" className={secundario} disabled={datos.pagina <= 1} onClick={() => setPagina(datos.pagina - 1)}>Anterior</button>
              <button type="button" className={secundario} disabled={datos.pagina >= datos.paginas} onClick={() => setPagina(datos.pagina + 1)}>Siguiente</button>
            </div>
          </nav>
        </>
      )}
    </div>
  );
}
