// P03. Registrar requerimiento, paso 2: especificaciones y documentos (cambio 15 de la
// Práctica 7, estados E a H de la Figura 21). Solo se habilita con semáforo vigente verde;
// al enviar, el requerimiento pasa a la bandeja de la Gerencia de Administración (P08).
import { useEffect, useState } from "react";
import { api, ErrorApi, type Detalle, type Documentos } from "../lib/api";
import { formatoFechaHora, formatoSoles } from "../lib/formato";
import PasosRegistro from "./PasosRegistro";

const campo = "w-full rounded border border-linea bg-white px-3 py-2";
const etiqueta = "mb-1 block text-sm font-semibold";
const SIN_DOCUMENTOS: Documentos = {
  documento_requerimiento_firmado: false, cuadro_necesidades: false, especificaciones_tecnicas_tdr: false,
};

export default function Paso2Requerimiento({ id }: { id: number }) {
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [errorCarga, setErrorCarga] = useState("");
  const [especificaciones, setEspecificaciones] = useState<Record<number, string>>({});
  const [plazo, setPlazo] = useState("");
  const [lugar, setLugar] = useState("");
  const [documentos, setDocumentos] = useState<Documentos>(SIN_DOCUMENTOS);
  const [errorDocumentos, setErrorDocumentos] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  useEffect(() => {
    api.detalle(id).then((d) => {
      setDetalle(d);
      setEspecificaciones(Object.fromEntries(d.items.map((i) => [i.id_item, i.especificacion ?? ""])));
      setPlazo(d.plazo_entrega_dias ? String(d.plazo_entrega_dias) : "");
      setLugar(d.lugar_entrega ?? "");
    }).catch((e: ErrorApi) => setErrorCarga(e.message));
  }, [id]);

  if (errorCarga) return <p role="alert" className="rounded border border-rojo bg-rojo-suave p-3">{errorCarga}</p>;
  if (!detalle) return <p className="text-pizarra">Cargando el requerimiento…</p>;

  const verde = detalle.semaforo_vigente === "VERDE";
  const servicio = detalle.objeto_contratacion === "SERVICIO";
  const datos = () => ({
    items: detalle.items.map((i) => ({ id_item: i.id_item, especificacion: especificaciones[i.id_item]?.trim() || null })),
    plazo_entrega_dias: Number(plazo) > 0 ? Math.trunc(Number(plazo)) : null,
    lugar_entrega: lugar.trim() || null,
  });
  const completo = detalle.items.every((i) => (especificaciones[i.id_item] ?? "").trim() !== "")
    && Number(plazo) > 0 && Number.isInteger(Number(plazo)) && lugar.trim() !== "";
  const todosLosDocumentos = Object.values(documentos).every(Boolean);

  async function guardar() {
    setOcupado(true); setMensaje(null);
    try {
      await api.guardarPaso2(id, datos());
      setMensaje({ tipo: "ok", texto: "Paso 2 guardado. Puede continuar después desde el detalle del requerimiento." });
    } catch (e) {
      setMensaje({ tipo: "error", texto: (e as ErrorApi).message });
    } finally {
      setOcupado(false);
    }
  }

  function pedirConfirmacion() {
    if (!todosLosDocumentos) { setErrorDocumentos(true); return; }  // estado G
    setErrorDocumentos(false);
    setConfirmar(true);  // estado H
  }

  async function enviar() {
    setOcupado(true); setMensaje(null);
    try {
      await api.enviar(id, { ...datos(), documentos });
      window.location.href = `/requerimientos/detalle?id=${id}&enviado=1`;
    } catch (e) {
      setMensaje({ tipo: "error", texto: (e as ErrorApi).message });
      setConfirmar(false);
      setOcupado(false);
    }
  }

  const cabecera = (
    <p className={`flex items-start gap-2 rounded border p-3 text-sm ${verde ? "border-verde bg-verde-suave" : "border-rojo bg-rojo-suave"}`}>
      <span aria-hidden className={`mt-1 h-3 w-3 shrink-0 rounded-full ${verde ? "bg-verde" : "bg-rojo"}`} />
      <span>
        <strong>{detalle.codigo}</strong> · {detalle.descripcion} — <span className="cifra">{formatoSoles(detalle.monto_estimado)}</span>
        <br />
        {verde
          ? <><strong>Verde{detalle.confirmado_por_presupuesto ? " · Confirmado por Presupuesto" : ""}:</strong> saldo presupuestal suficiente. Validación del {formatoFechaHora(detalle.semaforo.fecha_hora)}</>
          : <><strong>{detalle.semaforo_vigente === "ROJO" ? "Rojo" : "Ámbar"}:</strong> {detalle.semaforo_vigente === "ROJO" ? "el saldo no alcanza." : "pendiente de la decisión de Presupuesto."}</>}
      </span>
    </p>
  );

  // Estado F: paso 2 bloqueado si el semáforo vigente no es verde.
  if (!verde || detalle.fecha_envio) {
    return (
      <div className="max-w-5xl space-y-4">
        <PasosRegistro actual={detalle.fecha_envio ? 3 : 2} />
        {cabecera}
        <div className="rounded border border-dashed border-linea bg-superficie p-4 text-sm">
          {detalle.fecha_envio
            ? <p>El requerimiento ya fue enviado a la Gerencia de Administración el {formatoFechaHora(detalle.fecha_envio)}</p>
            : <p><strong>Paso 2 no disponible:</strong> las especificaciones y los documentos se completan solo cuando el
                semáforo vigente es verde. Aplique un ajuste o espere la decisión de Presupuesto si está en ámbar.</p>}
          <div className="mt-3 flex justify-end gap-3">
            <a href={`/requerimientos/detalle?id=${id}`} className="rounded border border-linea px-4 py-2 hover:bg-fondo">Ver el detalle</a>
            {detalle.semaforo_vigente === "ROJO" && (
              <button type="button" disabled title="La pantalla P05 se implementa en el siguiente incremento"
                className="cursor-not-allowed rounded bg-accion px-4 py-2 font-semibold text-white opacity-50">Ir a Aplicar ajuste</button>
            )}
            <button type="button" disabled className="cursor-not-allowed rounded border border-linea px-4 py-2 opacity-50">
              Enviar a la Gerencia
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Estado E: paso 2 habilitado.
  return (
    <div className="max-w-5xl space-y-4">
      <PasosRegistro actual={2} />
      {cabecera}
      {mensaje && (
        <p role={mensaje.tipo === "error" ? "alert" : "status"}
          className={`rounded border p-3 text-sm ${mensaje.tipo === "error" ? "border-rojo bg-rojo-suave" : "border-verde bg-verde-suave"}`}>
          {mensaje.texto}
        </p>
      )}
      <div className="space-y-5 rounded border border-linea bg-superficie p-5">
        <div>
          <p className={etiqueta}>Especificación técnica de cada ítem *</p>
          <table className="w-full text-sm">
            <thead className="bg-fondo text-left">
              <tr><th className="w-10 p-2">N.°</th><th className="w-1/3 p-2">Ítem (del paso 1, no editable)</th>
                <th className="p-2">Especificación técnica (características, calidad, norma aplicable)</th></tr>
            </thead>
            <tbody>
              {detalle.items.map((i, n) => (
                <tr key={i.id_item} className="border-b border-linea align-top">
                  <td className="p-2">{n + 1}</td>
                  <td className="p-2">{i.descripcion} · <span className="cifra">{Number(i.cantidad).toLocaleString("es-PE")}</span> {i.unidad_medida}</td>
                  <td className="p-1">
                    <textarea aria-label={`Especificación técnica del ítem ${n + 1}`} className={campo} rows={2} maxLength={1000}
                      value={especificaciones[i.id_item] ?? ""}
                      onChange={(e) => setEspecificaciones({ ...especificaciones, [i.id_item]: e.target.value })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-xs text-pizarra">No escriba nombres de personas.</p>
        </div>

        <div className="grid gap-5 md:grid-cols-[17rem_1fr]">
          <div>
            <label htmlFor="plazo" className={etiqueta}>Plazo de entrega (días calendario) *</label>
            <input id="plazo" type="number" min="1" step="1" className={`${campo} cifra`} value={plazo}
              onChange={(e) => setPlazo(e.target.value)} />
          </div>
          <div>
            <label htmlFor="lugar" className={etiqueta}>Lugar de entrega *</label>
            <input id="lugar" className={campo} maxLength={250} value={lugar} onChange={(e) => setLugar(e.target.value)} />
          </div>
        </div>

        <fieldset>
          <legend className={etiqueta}>Documentos que se adjuntan al expediente físico *</legend>
          <div className="space-y-1 text-sm">
            {([
              ["documento_requerimiento_firmado", "Documento de requerimiento firmado por el jefe de la unidad"],
              ["cuadro_necesidades", "Cuadro de necesidades"],
              ["especificaciones_tecnicas_tdr", servicio ? "Términos de referencia (servicio)" : "Especificaciones técnicas (bien)"],
            ] as const).map(([clave, texto]) => (
              <label key={clave} className="flex items-center gap-2">
                <input type="checkbox" checked={documentos[clave]}
                  onChange={(e) => { setDocumentos({ ...documentos, [clave]: e.target.checked }); setErrorDocumentos(false); }} />
                {texto}
              </label>
            ))}
          </div>
          {errorDocumentos && (
            <p role="alert" className="mt-2 text-sm text-rojo">
              Marque todos los documentos obligatorios que adjunta al expediente físico.
            </p>
          )}
        </fieldset>

        <div className="border-t border-linea pt-4">
          <div className="flex flex-wrap justify-end gap-3">
            <a href={`/requerimientos/detalle?id=${id}`} className="rounded border border-linea px-4 py-2 hover:bg-fondo">Volver</a>
            <button type="button" onClick={guardar} disabled={ocupado}
              className="rounded border border-accion px-4 py-2 text-accion hover:bg-fondo disabled:opacity-40">
              Guardar y continuar después
            </button>
            <button type="button" onClick={pedirConfirmacion} disabled={!completo || ocupado}
              className="rounded bg-accion px-4 py-2 font-semibold text-white hover:bg-accion-hover disabled:cursor-not-allowed disabled:opacity-40">
              Enviar a la Gerencia de Administración
            </button>
          </div>
          <p className="mt-2 text-right text-xs text-pizarra">
            Logística revisará estos documentos en la validación documental. El presupuesto ya no se vuelve a validar al enviar.
          </p>
        </div>
      </div>

      {confirmar && (
        <div role="dialog" aria-modal="true" aria-labelledby="titulo-confirmar"
          className="fixed inset-0 z-10 flex items-center justify-center bg-tinta/40 p-4">
          <div className="max-w-md rounded border border-linea bg-superficie p-5 shadow-lg">
            <h2 id="titulo-confirmar" className="font-semibold">¿Enviar a la Gerencia de Administración?</h2>
            <p className="mt-2 text-sm">
              {detalle.codigo} pasará a la bandeja de aprobación con sus especificaciones. Desde ese momento corre el plazo
              de 24 horas de la Gerencia.
            </p>
            <div className="mt-4 flex justify-end gap-3">
              <button type="button" onClick={() => setConfirmar(false)} disabled={ocupado}
                className="rounded border border-linea px-4 py-2 hover:bg-fondo">Cancelar</button>
              <button type="button" onClick={enviar} disabled={ocupado} autoFocus
                className="rounded bg-accion px-4 py-2 font-semibold text-white hover:bg-accion-hover disabled:opacity-40">
                {ocupado ? "Enviando…" : "Sí, enviar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
