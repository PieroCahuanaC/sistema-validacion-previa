// P11. Panel de alertas del Jefe de Presupuesto (CU-06, RF-09; Tabla 12 de la Práctica 7).
// Ámbar: confirmar o denegar la disponibilidad con sustento. Rojo: solo consulta, porque el
// ajuste le corresponde al Área Usuaria.
import { useEffect, useState } from "react";
import { api, ErrorApi, type Alerta } from "../lib/api";
import { formatoFecha, formatoFechaHora, formatoSoles } from "../lib/formato";
import { AreaObservacion, Aviso, Confirmacion, MOTIVO_CORTO, parametro, principal } from "./comunes";

type Pestana = "ambar" | "rojo";

export default function PanelAlertas() {
  const [datos, setDatos] = useState<{ ambar: Alerta[]; rojo: Alerta[] } | null>(null);
  const [pestana, setPestana] = useState<Pestana>("ambar");
  const [elegido, setElegido] = useState<number | null>(Number(parametro("id")) || null);
  const [resultado, setResultado] = useState<"CONFIRMADA" | "DENEGADA" | null>(null);
  const [sustento, setSustento] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  const cargar = () => api.alertas().then((d) => {
    setDatos(d);
    setElegido((actual) => (actual && d.ambar.some((a) => a.requerimiento_id === actual) ? actual : d.ambar[0]?.requerimiento_id ?? null));
  }).catch((e: ErrorApi) => setAviso({ tipo: "error", texto: e.message }));
  useEffect(() => { cargar(); }, []);

  const alerta = datos?.ambar.find((a) => a.requerimiento_id === elegido) ?? null;
  const lista = datos ? datos[pestana] : [];
  const valido = resultado === "CONFIRMADA" || (resultado === "DENEGADA" && sustento.trim().length > 0);

  async function registrar() {
    if (!alerta || !resultado) return;
    setOcupado(true);
    try {
      await api.decidir(alerta.requerimiento_id, resultado, sustento.trim());
      setAviso({ tipo: "ok", texto: resultado === "CONFIRMADA"
        ? `Disponibilidad de ${alerta.codigo} confirmada: su semáforo vigente es verde y el Área Usuaria puede continuar.`
        : `Disponibilidad de ${alerta.codigo} denegada: el Área Usuaria verá la acción Anular en sus pendientes.` });
      setResultado(null); setSustento(""); setConfirmar(false); setElegido(null);
      await cargar();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as ErrorApi).message });
      setConfirmar(false);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="space-y-4">
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
      <div role="tablist" aria-label="Alertas" className="flex gap-2 border-b border-linea">
        {(["ambar", "rojo"] as const).map((p) => (
          <button key={p} type="button" role="tab" aria-selected={pestana === p} onClick={() => setPestana(p)}
            className={`-mb-px rounded-t border px-4 py-2 font-semibold ${pestana === p ? "border-linea border-b-superficie bg-superficie" : "border-transparent text-pizarra"}`}>
            {p === "ambar" ? "Ámbar sin decisión" : "Rojo"} <span className="cifra">({datos ? datos[p].length : "…"})</span>
          </button>
        ))}
      </div>
      {pestana === "rojo" && (
        <Aviso tipo="info">Solo consulta: el ajuste de un requerimiento en rojo le corresponde al Área Usuaria (P05).</Aviso>
      )}

      {datos === null ? <p className="text-pizarra">Cargando alertas…</p> : lista.length === 0 ? (
        <p className="rounded border border-linea bg-superficie p-4 text-pizarra">No hay alertas pendientes.</p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-5">
          <section className={`overflow-x-auto rounded border border-linea bg-superficie ${pestana === "ambar" ? "xl:col-span-3" : "xl:col-span-5"}`}>
            <table className="w-full text-left text-sm">
              <thead className="bg-fondo text-pizarra">
                <tr><th scope="col" className="px-3 py-2">Código</th><th scope="col" className="px-3 py-2">Unidad</th>
                  <th scope="col" className="px-3 py-2">Meta</th><th scope="col" className="px-3 py-2 text-right">Monto evaluado</th>
                  <th scope="col" className="px-3 py-2">Motivo</th><th scope="col" className="px-3 py-2">Fecha de corte</th>
                  <th scope="col" className="px-3 py-2">Días en alerta</th>
                  {pestana === "rojo" && <th scope="col" className="px-3 py-2">Ajuste</th>}</tr>
              </thead>
              <tbody>
                {lista.map((a) => (
                  <tr key={a.requerimiento_id} onClick={() => pestana === "ambar" && setElegido(a.requerimiento_id)}
                    className={`border-t border-linea ${pestana === "ambar" ? "cursor-pointer" : ""} ${a.requerimiento_id === elegido && pestana === "ambar" ? "bg-fondo" : ""}`}>
                    <td className="px-3 py-2 font-semibold whitespace-nowrap">
                      {pestana === "ambar" ? (
                        <button type="button" className="hover:underline" aria-pressed={a.requerimiento_id === elegido}
                          onClick={() => setElegido(a.requerimiento_id)}>{a.codigo}</button>
                      ) : <a className="hover:underline" href={`/requerimientos/detalle?id=${a.requerimiento_id}`}>{a.codigo}</a>}
                    </td>
                    <td className="px-3 py-2">{a.unidad_sigla}</td>
                    <td className="px-3 py-2">{a.meta_codigo}</td>
                    <td className="cifra px-3 py-2 text-right">{formatoSoles(a.monto_evaluado)}</td>
                    <td className="px-3 py-2">{MOTIVO_CORTO[a.motivo] ?? a.motivo}</td>
                    <td className="px-3 py-2">{a.fecha_corte ? formatoFecha(a.fecha_corte) : "Sin datos"}</td>
                    <td className="cifra px-3 py-2">{a.dias_en_alerta}</td>
                    {pestana === "rojo" && <td className="px-3 py-2">{a.opcion_ajuste === "NINGUNA" ? "Ninguna (por anular)" : a.opcion_ajuste ?? "Pendiente"}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {pestana === "ambar" && alerta && (
            <section aria-label={`Decisión sobre ${alerta.codigo}`} className="space-y-3 rounded border border-ambar bg-superficie p-4 xl:col-span-2">
              <h2 className="text-lg font-bold">{alerta.codigo}</h2>
              <p className="text-sm">{alerta.descripcion}</p>
              <p className="text-sm text-pizarra">Validado el {formatoFechaHora(alerta.fecha_validacion)} · {alerta.estado_actual}</p>
              <p className="text-sm">
                <a className="font-semibold text-accion hover:underline" href={`/requerimientos/detalle?id=${alerta.requerimiento_id}`}>Ver detalle completo</a>
              </p>
              <fieldset>
                <legend className="mb-1 text-sm font-semibold">Resultado *</legend>
                <label className="mr-4 text-sm"><input type="radio" name="resultado" className="mr-1" checked={resultado === "CONFIRMADA"}
                  onChange={() => setResultado("CONFIRMADA")} />Confirmar disponibilidad</label>
                <label className="text-sm"><input type="radio" name="resultado" className="mr-1" checked={resultado === "DENEGADA"}
                  onChange={() => setResultado("DENEGADA")} />Denegar disponibilidad</label>
              </fieldset>
              <AreaObservacion id="sustento" texto="Sustento" valor={sustento} onChange={setSustento} obligatoria={resultado === "DENEGADA"}
                ayuda="Obligatorio si deniega." />
              <div className="flex justify-end">
                <button type="button" className={principal} disabled={!valido} onClick={() => setConfirmar(true)}>Registrar decisión</button>
              </div>
            </section>
          )}
        </div>
      )}

      {confirmar && alerta && resultado && (
        <Confirmacion titulo={resultado === "CONFIRMADA" ? "¿Confirmar la disponibilidad?" : "¿Denegar la disponibilidad?"}
          textoAccion="Registrar decisión" tipo={resultado === "DENEGADA" ? "peligro" : "principal"} ocupado={ocupado}
          onConfirmar={registrar} onCancelar={() => setConfirmar(false)}>
          <p>{resultado === "CONFIRMADA"
            ? <>El semáforo vigente de <strong>{alerta.codigo}</strong> pasará a verde y el Área Usuaria podrá completar el paso 2.</>
            : <>El Área Usuaria solo podrá anular <strong>{alerta.codigo}</strong>.</>}</p>
          <p className="font-semibold">La decisión no se puede modificar una vez registrada.</p>
        </Confirmacion>
      )}
    </div>
  );
}
