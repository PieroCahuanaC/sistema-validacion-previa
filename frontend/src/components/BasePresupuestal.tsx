// P15. Estado de la base presupuestal y carga CSV de respaldo (RF-14; riesgo R01; Figura 16 y
// Tabla 16 de la Práctica 7). Primero se valida el archivo (vista previa, sin escribir nada) y
// solo entonces se habilita «Cargar» (H5); el servidor lo vuelve a validar completo.
import { useEffect, useState } from "react";
import {
  api, ErrorApi, type BasePresupuestal as DatosBase, type Carga, type CargaEntrada, type ValidacionCarga,
} from "../lib/api";
import { formatoFecha, formatoFechaHora, formatoSoles, hoyLima } from "../lib/formato";
import { Aviso, campo, Confirmacion, etiqueta, principal, secundario } from "./comunes";

type Fuente = "MEF" | "SEACE";
const NOMBRE_FUENTE: Record<Fuente, string> = { MEF: "Consulta Amigable del MEF", SEACE: "SEACE (PAC)" };
const EJEMPLO: Record<Fuente, string> = {
  MEF: "0012,Mantenimiento de vías vecinales,180000.00,152000.00,148500.00",
  SEACE: "PAC-001,Adquisición de asfalto en frío,BIEN,40000.00",
};
const MAX_BYTES = 2_000_000;
const TITULO_COLUMNA: Record<string, string> = {
  codigo: "Meta", nombre: "Nombre", pim: "PIM", certificacion: "Certificación", compromiso_anual: "Compromiso anual",
  numero_referencia: "Referencia", descripcion: "Descripción", tipo_objeto: "Tipo", valor_estimado: "Valor estimado",
};
const MONTOS = new Set(["pim", "certificacion", "compromiso_anual", "valor_estimado"]);
const RESULTADO: Record<Carga["resultado"], string> = {
  EXITOSA: "border-verde bg-verde-suave text-verde", RECHAZADA: "border-rojo bg-rojo-suave text-rojo", FALLIDA: "border-rojo bg-rojo-suave text-rojo",
};

function Resultado({ valor }: { valor: Carga["resultado"] }) {
  const texto = { EXITOSA: "Exitosa", RECHAZADA: "Rechazada", FALLIDA: "Fallida" }[valor];
  return <span className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold ${RESULTADO[valor]}`}>{texto}</span>;
}
const origen = (o: Carga["origen"]) => (o === "AUTOMATICA" ? "Automática" : "Carga manual (CSV)");

/** Lee el archivo como UTF-8 y, si no lo es (CSV guardado por Excel), como Windows-1252. */
async function leer(archivo: File): Promise<string> {
  const bytes = await archivo.arrayBuffer();
  try { return new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch { return new TextDecoder("windows-1252").decode(bytes); }
}

function descargarPlantilla(fuente: Fuente, columnas: string[]) {
  const texto = `${columnas.join(",")}\n${EJEMPLO[fuente]}\n`;
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(new Blob([texto], { type: "text/csv;charset=utf-8" }));
  enlace.download = `plantilla_${fuente.toLowerCase()}.csv`;
  enlace.click();
  URL.revokeObjectURL(enlace.href);
}

export default function BasePresupuestal() {
  const [datos, setDatos] = useState<DatosBase | null>(null);
  const [fuente, setFuente] = useState<Fuente>("MEF");
  const [anio, setAnio] = useState("");
  const [corte, setCorte] = useState(hoyLima());
  const [archivo, setArchivo] = useState<File | null>(null);
  const [previa, setPrevia] = useState<ValidacionCarga | null>(null);
  const [validado, setValidado] = useState<CargaEntrada | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [claveArchivo, setClaveArchivo] = useState(0);

  const actualizar = () => api.basePresupuestal().then((d) => {
    setDatos(d); setAnio((a) => a || String(d.anio_fiscal));
  }).catch((e: ErrorApi) => setAviso({ tipo: "error", texto: e.message }));
  useEffect(() => { actualizar(); }, []);

  // Cualquier cambio en el formulario invalida la vista previa: hay que validar de nuevo.
  const tocar = () => { setPrevia(null); setValidado(null); setAviso(null); };

  const validar = async () => {
    if (!archivo) return;
    setAviso(null);
    if (archivo.size > MAX_BYTES) { setAviso({ tipo: "error", texto: "El archivo supera los 2 MB permitidos." }); return; }
    setOcupado(true);
    try {
      const entrada: CargaEntrada = { fuente, anio_fiscal: Number(anio), fecha_corte: corte, contenido: await leer(archivo) };
      const r = await api.validarCarga(entrada);
      setPrevia(r); setValidado(r.valido ? entrada : null);
    } catch (e) {
      setPrevia(null); setValidado(null);
      const error = e as ErrorApi;
      setAviso({ tipo: "error", texto: error.errores.length ? `${error.message} ${error.errores.map((x) => x.mensaje).join(" ")}` : error.message });
    } finally { setOcupado(false); }
  };

  const cargar = async () => {
    if (!validado) return;
    setOcupado(true);
    try {
      const r = await api.cargar(validado);
      setConfirmar(false); setPrevia(null); setValidado(null); setArchivo(null); setClaveArchivo((k) => k + 1);
      setAviso({ tipo: "ok", texto: `Carga registrada: ${r.filas} fila(s) de ${NOMBRE_FUENTE[r.carga.fuente]} con corte al ${formatoFecha(r.carga.fecha_corte)}. ${
        r.vigente ? "Desde ahora el sistema valida con estos datos." : "Quedó en el historial; la carga vigente tiene una fecha de corte posterior."}` });
      await actualizar();
    } catch (e) {
      setConfirmar(false);
      setAviso({ tipo: "error", texto: (e as ErrorApi).message });
      await actualizar();
    } finally { setOcupado(false); }
  };

  if (!datos) return aviso ? <Aviso tipo="error">{aviso.texto}</Aviso> : <p className="text-pizarra">Cargando…</p>;
  const columnas = datos.columnas[fuente];
  const sinAutomatica = !datos.historial.some((c) => c.origen === "AUTOMATICA");

  return (
    <div className="space-y-6">
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}

      <section aria-label="Estado de las fuentes" className="grid gap-4 lg:grid-cols-2">
        {datos.fuentes.map((f) => (
          <div key={f.fuente} className="rounded border border-linea bg-superficie p-4">
            <h2 className="font-semibold">{f.nombre}</h2>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
              <dt className="text-pizarra">Última ejecución</dt>
              <dd>{f.ultima_ejecucion ? <>{formatoFechaHora(f.ultima_ejecucion.fecha_ejecucion)} · {origen(f.ultima_ejecucion.origen)} <Resultado valor={f.ultima_ejecucion.resultado} /></> : "Sin cargas este año"}</dd>
              <dt className="text-pizarra">Datos vigentes al</dt>
              <dd><strong>{f.ultima_exitosa ? formatoFecha(f.ultima_exitosa.fecha_corte) : "Sin datos"}</strong>
                {f.dias_desde_corte !== null && <span className="text-pizarra"> ({f.dias_desde_corte === 0 ? "hoy" : `hace ${f.dias_desde_corte} día${f.dias_desde_corte === 1 ? "" : "s"}`})</span>}</dd>
            </dl>
            {f.desactualizado && (
              <div className="mt-3"><Aviso tipo="atencion">
                {f.ultima_exitosa ? `El dato del MEF supera la antigüedad máxima de ${datos.antiguedad_maxima_dias} días de la regla vigente`
                  : "No hay saldos del MEF para el año en curso"}: los requerimientos nuevos saldrán en ámbar. Cargue un archivo actualizado.
              </Aviso></div>
            )}
          </div>
        ))}
      </section>
      {sinAutomatica && (
        <p className="text-sm text-pizarra">La extracción automática diaria todavía no está activa: mientras tanto, la base se actualiza con la carga manual de abajo.</p>
      )}

      <section aria-labelledby="titulo-carga" className="space-y-4 rounded border border-linea bg-superficie p-5">
        <h2 id="titulo-carga" className="text-lg font-semibold">Carga manual de respaldo (CSV)</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <fieldset>
            <legend className={etiqueta}>Fuente *</legend>
            <div className="flex gap-4 pt-2 text-sm">
              {(["MEF", "SEACE"] as Fuente[]).map((x) => (
                <label key={x} className="flex items-center gap-2"><input type="radio" name="fuente" checked={fuente === x}
                  onChange={() => { setFuente(x); tocar(); }} />{x === "MEF" ? "MEF (saldos)" : "SEACE (PAC)"}</label>
              ))}
            </div>
          </fieldset>
          <div>
            <label htmlFor="c-anio" className={etiqueta}>Año fiscal *</label>
            <input id="c-anio" type="number" min={2024} max={datos.anio_fiscal} className={campo} value={anio}
              onChange={(e) => { setAnio(e.target.value); tocar(); }} />
          </div>
          <div>
            <label htmlFor="c-corte" className={etiqueta}>Fecha de corte *</label>
            <input id="c-corte" type="date" max={hoyLima()} className={campo} value={corte}
              onChange={(e) => { setCorte(e.target.value); tocar(); }} />
          </div>
          <div>
            <label htmlFor="c-archivo" className={etiqueta}>Archivo .csv *</label>
            <input key={claveArchivo} id="c-archivo" type="file" accept=".csv,text/csv" className="block w-full text-sm"
              onChange={(e) => { setArchivo(e.target.files?.[0] ?? null); tocar(); }} />
          </div>
        </div>
        <div className="rounded bg-fondo p-3 text-sm">
          <p>Columnas esperadas, en la primera fila: <code className="font-semibold">{columnas.join(", ")}</code>.</p>
          <p className="mt-1 text-pizarra">Se acepta el CSV de Excel (separado por punto y coma, con coma decimal). Un solo error rechaza todo el archivo: no se carga nada a medias.
            {" "}<button type="button" className="font-semibold text-accion hover:underline" onClick={() => descargarPlantilla(fuente, columnas)}>Descargar plantilla</button></p>
        </div>
        <div className="flex justify-end gap-3">
          <button type="button" className={secundario} disabled={!archivo || !corte || !anio || ocupado} onClick={validar}>Validar archivo</button>
          <button type="button" className={principal} disabled={!validado || ocupado} onClick={() => setConfirmar(true)}>Cargar</button>
        </div>

        {previa && !previa.valido && (
          <Aviso tipo="error">
            <p className="font-semibold">El archivo tiene {previa.total_errores} error(es). No se cargó ningún dato.</p>
            <ul className="mt-2 list-disc space-y-0.5 pl-5">{previa.errores.map((e) => <li key={e}>{e}</li>)}</ul>
            {previa.total_errores > previa.errores.length && <p className="mt-1">… y {previa.total_errores - previa.errores.length} más.</p>}
          </Aviso>
        )}
        {previa?.valido && (
          <div className="space-y-3">
            <Aviso tipo="ok">Archivo válido: {previa.total_filas} fila(s). Revise la vista previa y pulse «Cargar».</Aviso>
            {previa.avisos.map((a) => <Aviso key={a} tipo="atencion">{a}</Aviso>)}
            <div className="overflow-x-auto rounded border border-linea">
              <table className="w-full text-left text-sm">
                <caption className="px-3 py-2 text-left text-pizarra">Vista previa: {previa.vista_previa.length} de {previa.total_filas} fila(s)</caption>
                <thead className="bg-fondo text-pizarra"><tr>{Object.keys(previa.vista_previa[0] ?? {}).map((c) => (
                  <th key={c} scope="col" className={`px-3 py-2 ${MONTOS.has(c) ? "text-right" : ""}`}>{TITULO_COLUMNA[c] ?? c}{MONTOS.has(c) ? " (S/)" : ""}</th>))}</tr></thead>
                <tbody>{previa.vista_previa.map((fila, i) => (
                  <tr key={i} className="border-t border-linea">{Object.entries(fila).map(([c, v]) => (
                    <td key={c} className={`px-3 py-1.5 ${MONTOS.has(c) ? "cifra text-right" : ""}`}>{MONTOS.has(c) ? formatoSoles(v) : v}</td>))}</tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      <section aria-labelledby="titulo-historial">
        <h2 id="titulo-historial" className="mb-3 text-lg font-semibold">Historial de cargas</h2>
        <div className="overflow-x-auto rounded border border-linea bg-superficie">
          <table className="w-full text-left text-sm">
            <thead className="bg-fondo text-pizarra">
              <tr><th scope="col" className="px-3 py-2">Ejecución</th><th scope="col" className="px-3 py-2">Fuente</th>
                <th scope="col" className="px-3 py-2">Origen</th><th scope="col" className="px-3 py-2">Año</th>
                <th scope="col" className="px-3 py-2">Corte</th><th scope="col" className="px-3 py-2">Resultado</th>
                <th scope="col" className="px-3 py-2">Detalle</th></tr>
            </thead>
            <tbody>
              {datos.historial.map((c) => (
                <tr key={c.id_carga} className="border-t border-linea align-top">
                  <td className="px-3 py-2 whitespace-nowrap">{formatoFechaHora(c.fecha_ejecucion)}</td>
                  <td className="px-3 py-2">{c.fuente}</td>
                  <td className="px-3 py-2">{origen(c.origen)}</td>
                  <td className="px-3 py-2">{c.anio_fiscal}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatoFecha(c.fecha_corte)}</td>
                  <td className="px-3 py-2"><Resultado valor={c.resultado} /></td>
                  <td className="max-w-md px-3 py-2 text-xs text-pizarra">{c.detalle_error ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {confirmar && validado && previa && (
        <Confirmacion titulo="¿Cargar este archivo?" textoAccion="Cargar" ocupado={ocupado} onConfirmar={cargar} onCancelar={() => setConfirmar(false)}>
          <p>Se registrarán {previa.total_filas} fila(s) de {NOMBRE_FUENTE[validado.fuente]} del año {validado.anio_fiscal}, con corte al {formatoFecha(validado.fecha_corte)}.</p>
          <p>El servidor validará el archivo otra vez antes de cargarlo. La carga queda en el historial y en la bitácora.</p>
        </Confirmacion>
      )}
    </div>
  );
}
