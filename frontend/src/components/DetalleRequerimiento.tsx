// P04. Detalle del requerimiento y semáforo (CU-04, RF-02, RF-03). Incluye el indicador de
// etapas del trámite con el responsable actual, que pidió el asesor en la Práctica 7.
import { useEffect, useState } from "react";
import { api, ErrorApi, type Detalle, type Etapa } from "../lib/api";
import { formatoFecha, formatoFechaHora, formatoSoles } from "../lib/formato";

const COLOR = {
  VERDE: { texto: "Verde", banda: "bg-verde text-white", suave: "bg-verde-suave border-verde" },
  AMBAR: { texto: "Ámbar", banda: "bg-ambar text-white", suave: "bg-ambar-suave border-ambar" },
  ROJO: { texto: "Rojo", banda: "bg-rojo text-white", suave: "bg-rojo-suave border-rojo" },
} as const;

const MOTIVO: Record<string, string> = {
  DISPONIBLE: "El saldo presupuestal disponible de la meta cubre el monto evaluado. Puede continuar el trámite.",
  PRESUPUESTO_INSUFICIENTE: "Presupuesto insuficiente: el saldo presupuestal disponible de la meta no cubre el monto evaluado.",
  SIN_DATOS_META: "La meta no tiene saldo en la base presupuestal del sistema. El Jefe de Presupuesto debe confirmar la disponibilidad.",
  DATO_DESACTUALIZADO: "El dato presupuestal es más antiguo que lo permitido por la regla. El Jefe de Presupuesto debe confirmar la disponibilidad.",
  NO_PREVISTO_PAC: "El requerimiento no está previsto en el PAC. El Jefe de Presupuesto debe confirmar la disponibilidad.",
};

function Etapas({ etapas, responsable, accion }: { etapas: Etapa[]; responsable: string; accion: string }) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const detalle = etapas.find((e) => e.codigo === abierta);
  return (
    <section aria-label="Etapas del trámite" className="rounded border border-linea bg-superficie p-4">
      <h2 className="mb-3 font-semibold">Etapas del trámite</h2>
      <ol className="grid grid-cols-2 gap-2 md:grid-cols-6">
        {etapas.map((e, n) => (
          <li key={e.codigo}>
            <button type="button" disabled={!e.cumplida} onClick={() => setAbierta(abierta === e.codigo ? null : e.codigo)}
              aria-current={e.actual ? "step" : undefined} aria-expanded={abierta === e.codigo}
              className={`w-full rounded border p-2 text-left text-sm ${e.actual ? "border-accion bg-accion text-white"
                : e.cumplida ? "border-accion text-accion hover:bg-fondo" : "cursor-default border-linea text-pizarra/60"}`}>
              <span className="block font-semibold">{n + 1}. {e.nombre}</span>
              <span className="block text-xs">{e.rol_a_cargo}</span>
            </button>
          </li>
        ))}
      </ol>
      {detalle && (
        <p className="mt-3 rounded bg-fondo p-2 text-sm">
          {detalle.nombre}: {formatoFechaHora(detalle.fecha_hora)} · {detalle.rol_registro}
          {detalle.observacion ? ` · Proveído: ${detalle.observacion}` : ""}
        </p>
      )}
      <p className="mt-3 text-sm">
        Responsable actual: <strong>{responsable}</strong>. Acción pendiente: {accion}.
      </p>
    </section>
  );
}

function Fila({ etiqueta, valor, signo, fuerte }: { etiqueta: string; valor: string; signo?: string; fuerte?: boolean }) {
  return (
    <div className={`flex items-baseline justify-between gap-4 py-1 ${fuerte ? "border-t border-tinta font-bold" : ""}`}>
      <dt>{etiqueta}</dt>
      <dd className="cifra">{signo && <span className="mr-2 text-pizarra">{signo}</span>}{valor}</dd>
    </div>
  );
}

export default function DetalleRequerimiento() {
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [error, setError] = useState("");
  const [ayuda, setAyuda] = useState(false);
  const parametros = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  const registrado = parametros?.get("registrado") === "1";

  useEffect(() => {
    const id = Number(parametros?.get("id"));
    if (!id) { setError("Indique el requerimiento que desea consultar."); return; }
    api.detalle(id).then(setDetalle).catch((e: ErrorApi) => setError(e.message));
  }, []);

  if (error) return <p role="alert" className="rounded border border-rojo bg-rojo-suave p-3">{error}</p>;
  if (!detalle) return <p className="text-pizarra">Cargando el requerimiento…</p>;

  const s = detalle.semaforo;
  const b = s.base_calculo;
  const color = COLOR[s.estado];
  const columna = b.columna_comparacion === "CERTIFICACION" ? "Certificación" : "Compromiso anual";
  const restado = b.columna_comparacion === "CERTIFICACION" ? b.certificacion : b.compromiso_anual;

  return (
    <div className="max-w-5xl space-y-4">
      {registrado && (
        <p role="status" className="rounded border border-verde bg-verde-suave p-3 text-sm">
          Requerimiento {detalle.codigo} registrado. El sistema validó su disponibilidad presupuestal.
        </p>
      )}

      <Etapas etapas={detalle.etapas} responsable={detalle.responsable_actual} accion={detalle.accion_pendiente} />

      <section aria-label="Semáforo presupuestal" className={`overflow-hidden rounded border ${color.suave}`}>
        <div className={`flex flex-wrap items-center gap-3 px-4 py-3 ${color.banda}`}>
          <span className="text-2xl font-bold">Semáforo {color.texto}</span>
          <span className="text-sm opacity-90">Validado el {formatoFechaHora(s.fecha_hora)}</span>
          <button type="button" onClick={() => setAyuda(!ayuda)} aria-expanded={ayuda}
            className="ml-auto rounded-full border border-white/70 px-2.5 font-bold" title="¿Por qué este resultado?">?</button>
        </div>
        <div className="grid gap-6 p-4 md:grid-cols-2">
          <div>
            <p className="font-semibold">{MOTIVO[s.motivo] ?? s.motivo}</p>
            {ayuda && (
              <p className="mt-2 text-sm">
                El semáforo compara el monto evaluado con el saldo presupuestal disponible de la meta, que es el PIM menos el{" "}
                {columna.toLowerCase()}, según la última carga de la Consulta Amigable del MEF. Si el dato tiene más días de
                antigüedad que los permitidos o el requerimiento no está en el PAC, el resultado es ámbar.
              </p>
            )}
            <p className="mt-3 text-sm">
              Previsto en el PAC: <strong>{b.previsto_en_pac ? `Sí (${b.pac_item_referencia})` : "No"}</strong>
              <br />Fecha de corte del dato: <strong>{formatoFecha(b.fecha_corte)}</strong>
            </p>
            {s.opciones_ajuste.length > 0 && (
              <div className="mt-4">
                <button type="button" disabled title="La pantalla P05 se implementa en el siguiente incremento"
                  className="cursor-not-allowed rounded bg-accion px-4 py-2 font-semibold text-white opacity-50">Aplicar ajuste</button>
                <p className="mt-1 text-xs text-pizarra">Podrá reformular o reprogramar el requerimiento (siguiente incremento).</p>
              </div>
            )}
          </div>
          <dl aria-label="Base de cálculo" className="rounded bg-superficie p-3 text-sm">
            <Fila etiqueta="PIM de la meta" valor={formatoSoles(b.pim)} />
            <Fila etiqueta={columna} valor={formatoSoles(restado)} signo="−" />
            <Fila etiqueta="Saldo presupuestal disponible" valor={formatoSoles(b.saldo_disponible)} fuerte />
            <Fila etiqueta="Monto evaluado del requerimiento" valor={formatoSoles(b.monto_evaluado)} />
            <p className="mt-2 text-xs text-pizarra">El saldo es crédito presupuestario aún no comprometido, no dinero en caja.</p>
          </dl>
        </div>
      </section>

      <section aria-label="Datos del requerimiento" className="rounded border border-linea bg-superficie p-4">
        <h2 className="mb-2 font-semibold">{detalle.codigo} · {detalle.estado_actual}</h2>
        <dl className="grid gap-x-6 gap-y-1 text-sm md:grid-cols-2">
          <div><dt className="inline text-pizarra">Unidad orgánica: </dt><dd className="inline">{detalle.unidad_organica}</dd></div>
          <div><dt className="inline text-pizarra">Meta: </dt><dd className="inline">{detalle.meta_codigo} · {detalle.meta_nombre}</dd></div>
          <div><dt className="inline text-pizarra">Objeto: </dt><dd className="inline">{detalle.objeto_contratacion === "BIEN" ? "Bien" : "Servicio"}</dd></div>
          <div><dt className="inline text-pizarra">Fecha de necesidad: </dt><dd className="inline">{formatoFecha(detalle.fecha_necesidad)}</dd></div>
          <div className="md:col-span-2"><dt className="inline text-pizarra">Descripción: </dt><dd className="inline">{detalle.descripcion}</dd></div>
        </dl>
        <table className="mt-3 w-full text-sm">
          <thead className="bg-fondo text-left">
            <tr><th className="p-2">Ítem</th><th className="p-2">Unidad</th><th className="p-2 text-right">Cantidad</th>
              <th className="p-2 text-right">P. unit. ref.</th><th className="p-2 text-right">Subtotal</th></tr>
          </thead>
          <tbody>
            {detalle.items.map((i, n) => (
              <tr key={n} className="border-b border-linea">
                <td className="p-2">{i.descripcion}</td><td className="p-2">{i.unidad_medida}</td>
                <td className="cifra p-2 text-right">{Number(i.cantidad).toLocaleString("es-PE")}</td>
                <td className="cifra p-2 text-right">{formatoSoles(i.precio_unitario_ref)}</td>
                <td className="cifra p-2 text-right">{formatoSoles(i.subtotal)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td colSpan={4} className="p-2 text-right font-semibold">Monto estimado</td>
              <td className="cifra p-2 text-right font-bold">{formatoSoles(detalle.monto_estimado)}</td></tr>
          </tfoot>
        </table>
      </section>

      <div className="flex justify-end gap-3">
        <button type="button" disabled title="La pantalla P07 se implementa en el siguiente incremento"
          className="cursor-not-allowed rounded border border-linea px-4 py-2 opacity-50">Ver historial</button>
        <a href="/requerimientos/nuevo" className="rounded border border-linea px-4 py-2 hover:bg-superficie">Registrar otro requerimiento</a>
      </div>
    </div>
  );
}
