// P09. Validación documental (CU-07, RF-11; Tabla 10 de la Práctica 7). La revisión de los
// documentos es física; el sistema registra su resultado por documento.
import { useEffect, useState } from "react";
import { api, ErrorApi, type DocumentoRevision } from "../lib/api";
import { formatoFechaHora, formatoSoles } from "../lib/formato";
import { Aviso, campo, Confirmacion, principal, secundario } from "./comunes";
import { EnlacesExpediente, TablaExpedientes, useExpedientes } from "./ListaExpedientes";

type Resultado = { resultado: "CONFORME" | "OBSERVADO" | ""; observacion: string };

export default function ValidacionDocumental() {
  const { filas, fila, elegido, setElegido, cargar, error } = useExpedientes("APROBADO");
  const [documentos, setDocumentos] = useState<DocumentoRevision[]>([]);
  const [resultados, setResultados] = useState<Record<number, Resultado>>({});
  const [accion, setAccion] = useState<"VALIDAR" | "DEVOLVER" | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  useEffect(() => {
    if (!elegido) return;
    api.revision(elegido).then((r) => {
      setDocumentos(r.documentos);
      setResultados(Object.fromEntries(r.documentos.map((d) => [d.id_tipo_documento, { resultado: "", observacion: "" }])));
    }).catch((e: ErrorApi) => setAviso({ tipo: "error", texto: e.message }));
  }, [elegido]);

  const lista = documentos.map((d) => ({ d, r: resultados[d.id_tipo_documento] ?? { resultado: "", observacion: "" } }));
  const completos = lista.every(({ r }) => r.resultado && (r.resultado === "CONFORME" || r.observacion.trim()));
  const hayObservado = lista.some(({ r }) => r.resultado === "OBSERVADO");
  const puedeValidar = completos && lista.every(({ d, r }) => !d.obligatorio || r.resultado === "CONFORME");
  const poner = (id: number, cambio: Partial<Resultado>) => setResultados({ ...resultados, [id]: { ...resultados[id], ...cambio } });

  async function registrar() {
    if (!fila) return;
    setOcupado(true);
    try {
      const r = await api.registrarRevision(fila.requerimiento_id, lista.map(({ d, r }) => ({
        id_tipo_documento: d.id_tipo_documento, resultado: r.resultado,
        observacion: r.resultado === "OBSERVADO" ? r.observacion.trim() : undefined })));
      setAviso({ tipo: "ok", texto: r.resultado === "VALIDADA"
        ? `${r.codigo}: documentación validada. Ya puede elaborar el cuadro comparativo.`
        : `${r.codigo}: devuelto al Área Usuaria con las observaciones.` });
      setAccion(null);
      await cargar();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as ErrorApi).message });
      setAccion(null);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="space-y-4">
      {(aviso || error) && <Aviso tipo={aviso?.tipo ?? "error"}>{aviso?.texto ?? error}
        {aviso?.texto.includes("cuadro comparativo") && <> <a className="font-semibold underline" href="/cuadro">Ir al cuadro comparativo</a></>}</Aviso>}
      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <TablaExpedientes titulo="Aprobados por validar" filas={filas} elegido={elegido} onElegir={setElegido}
            vacio="No hay expedientes aprobados por validar." />
        </div>
        {fila && (
          <section aria-label={`Validación de ${fila.codigo}`} className="space-y-3 rounded border border-linea bg-superficie p-4 xl:col-span-3">
            <h2 className="text-lg font-bold">{fila.codigo}</h2>
            <p className="text-sm">{fila.descripcion}</p>
            <p className="text-sm text-pizarra">{fila.unidad_sigla} · Meta {fila.meta_codigo} · {fila.objeto_contratacion === "BIEN" ? "Bien" : "Servicio"} · {formatoSoles(fila.monto_estimado)}</p>
            <EnlacesExpediente id={fila.requerimiento_id} />
            <Aviso tipo="info">La revisión de los documentos es física, sobre el expediente; aquí se registra su resultado.</Aviso>
            <table className="w-full text-sm">
              <thead className="bg-fondo text-left">
                <tr><th className="p-2">Documento</th><th className="p-2">Resultado *</th><th className="p-2">Última revisión</th></tr>
              </thead>
              <tbody>
                {lista.map(({ d, r }) => (
                  <tr key={d.id_tipo_documento} className="border-b border-linea align-top">
                    <td className="p-2">{d.nombre}{d.obligatorio && <span className="block text-xs text-pizarra">Obligatorio</span>}</td>
                    <td className="p-2">
                      <fieldset>
                        <legend className="sr-only">Resultado de {d.nombre}</legend>
                        <label className="mr-3 whitespace-nowrap"><input type="radio" name={`doc-${d.id_tipo_documento}`} className="mr-1"
                          checked={r.resultado === "CONFORME"} onChange={() => poner(d.id_tipo_documento, { resultado: "CONFORME" })} />Conforme</label>
                        <label className="whitespace-nowrap"><input type="radio" name={`doc-${d.id_tipo_documento}`} className="mr-1"
                          checked={r.resultado === "OBSERVADO"} onChange={() => poner(d.id_tipo_documento, { resultado: "OBSERVADO" })} />Observado</label>
                      </fieldset>
                      {r.resultado === "OBSERVADO" && (
                        <textarea aria-label={`Observación de ${d.nombre}`} rows={2} maxLength={500} className={`${campo} mt-2`}
                          placeholder="Qué falta o qué corregir (obligatorio)" value={r.observacion}
                          onChange={(e) => poner(d.id_tipo_documento, { observacion: e.target.value })} />
                      )}
                    </td>
                    <td className="p-2 text-xs text-pizarra">
                      {d.ultimo_resultado ? <>{d.ultimo_resultado === "CONFORME" ? "Conforme" : "Observado"} · {formatoFechaHora(d.ultima_fecha)}
                        {d.ultima_observacion && <span className="block">{d.ultima_observacion}</span>}</> : "Sin revisión previa"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex flex-wrap justify-end gap-3">
              <button type="button" className={secundario} disabled={!completos || !hayObservado} onClick={() => setAccion("DEVOLVER")}>
                Devolver al Área Usuaria con observaciones</button>
              <button type="button" className={principal} disabled={!puedeValidar} onClick={() => setAccion("VALIDAR")}>
                Registrar validación conforme</button>
            </div>
          </section>
        )}
      </div>
      {accion && fila && (
        <Confirmacion titulo={accion === "VALIDAR" ? "¿Registrar la validación conforme?" : "¿Devolver al Área Usuaria?"}
          textoAccion={accion === "VALIDAR" ? "Registrar validación" : "Devolver"} ocupado={ocupado}
          onConfirmar={registrar} onCancelar={() => setAccion(null)}>
          <p>{accion === "VALIDAR"
            ? <>Los documentos de <strong>{fila.codigo}</strong> quedarán conformes y se habilitará el cuadro comparativo.</>
            : <><strong>{fila.codigo}</strong> volverá al Área Usuaria con las observaciones de cada documento.</>}</p>
          <p className="font-semibold">El cambio de estado no se puede deshacer.</p>
        </Confirmacion>
      )}
    </div>
  );
}
