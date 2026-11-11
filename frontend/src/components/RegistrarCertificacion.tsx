// P12. Registrar certificación emitida (CU-13, RF-05; Tabla 13 de la Práctica 7). La
// certificación es un acto administrativo que se emite fuera del sistema; aquí se registra que
// fue emitida. Presupuesto no ve los datos de los proveedores (datos personales).
import { useEffect, useState } from "react";
import { api, ErrorApi, type Cuadro } from "../lib/api";
import { formatoFecha, formatoFechaHora, formatoSoles } from "../lib/formato";
import { AreaObservacion, Aviso, Confirmacion, peligro, principal, secundario } from "./comunes";
import { EnlacesExpediente, TablaExpedientes, useExpedientes } from "./ListaExpedientes";

type Accion = "CERTIFICADO" | "DOCUMENTACION_VALIDADA" | "ANULADO";

export default function RegistrarCertificacion() {
  const { filas, fila, elegido, setElegido, cargar, error } = useExpedientes("CUADRO_REGISTRADO");
  const [cuadro, setCuadro] = useState<Cuadro | null>(null);
  const [emitida, setEmitida] = useState(false);
  const [texto, setTexto] = useState("");
  const [accion, setAccion] = useState<Accion | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  useEffect(() => {
    setEmitida(false); setTexto(""); setCuadro(null);
    if (elegido) api.cuadro(elegido).then(setCuadro).catch((e: ErrorApi) => setAviso({ tipo: "error", texto: e.message }));
  }, [elegido]);

  async function registrar() {
    if (!fila || !accion) return;
    setOcupado(true);
    try {
      await api.cambiarEtapa(fila.requerimiento_id, accion, texto.trim());
      setAviso({ tipo: "ok", texto: {
        CERTIFICADO: `${fila.codigo}: certificación registrada. Pasa a Logística para la orden.`,
        DOCUMENTACION_VALIDADA: `${fila.codigo}: devuelto a Logística para corregir el cuadro.`,
        ANULADO: `${fila.codigo}: anulado por falta de disponibilidad presupuestal.`,
      }[accion] });
      setAccion(null);
      await cargar();
    } catch (e) {
      setAviso({ tipo: "error", texto: (e as ErrorApi).message });
      setAccion(null);
    } finally {
      setOcupado(false);
    }
  }

  const verde = fila?.semaforo_vigente === "VERDE";
  return (
    <div className="space-y-4">
      {(aviso || error) && <Aviso tipo={aviso?.tipo ?? "error"}>{aviso?.texto ?? error}</Aviso>}
      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <TablaExpedientes titulo="Por certificar" filas={filas} elegido={elegido} onElegir={setElegido} precio
            vacio="No hay cuadros comparativos por certificar." />
        </div>
        {fila && (
          <section aria-label={`Certificación de ${fila.codigo}`} className="space-y-3 rounded border border-linea bg-superficie p-4 xl:col-span-3">
            <h2 className="text-lg font-bold">{fila.codigo}</h2>
            <p className="text-sm">{fila.descripcion}</p>
            <p className="text-sm text-pizarra">{fila.unidad_sigla} · Meta {fila.meta_codigo} · Monto estimado {formatoSoles(fila.monto_estimado)}</p>
            <EnlacesExpediente id={fila.requerimiento_id} />
            {fila.semaforo_vigente === "AMBAR_PENDIENTE" && (
              <Aviso tipo="atencion">Con el precio de mercado el semáforo quedó en ámbar. Confirme o deniegue la disponibilidad en el <a className="font-semibold underline" href={`/alertas?id=${fila.requerimiento_id}`}>Panel de alertas</a> antes de certificar.</Aviso>
            )}
            {fila.semaforo_vigente === "AMBAR_DENEGADO" && (
              <Aviso tipo="atencion">La disponibilidad fue denegada: corresponde anular el requerimiento por falta de disponibilidad.</Aviso>
            )}
            {cuadro && (
              <div className="rounded border border-linea p-3 text-sm">
                <h3 className="font-semibold">Cuadro comparativo · registrado el {formatoFechaHora(cuadro.fecha_registro)}</h3>
                <table className="mt-2 w-full">
                  <thead className="text-left text-pizarra"><tr><th className="py-1">Cotización</th><th className="py-1">Fecha</th><th className="py-1 text-right">Monto</th></tr></thead>
                  <tbody>{cuadro.cotizaciones.map((c, n) => (
                    <tr key={c.id_cotizacion} className="border-t border-linea"><td className="py-1">Proveedor {n + 1}</td>
                      <td className="py-1">{formatoFecha(c.fecha_cotizacion)}</td><td className="cifra py-1 text-right">{formatoSoles(c.monto)}</td></tr>
                  ))}</tbody>
                </table>
                <p className="mt-2">Precio de referencia: <strong className="cifra">{formatoSoles(cuadro.precio_referencia)}</strong></p>
                {cuadro.observacion && <p className="text-pizarra">Criterio: {cuadro.observacion}</p>}
                <p className="mt-1 text-xs text-pizarra">Los datos de los proveedores no se muestran por ser datos personales.</p>
              </div>
            )}
            <Aviso tipo="info">La certificación presupuestaria se emite como acto administrativo fuera del sistema. Aquí solo se registra que fue emitida.</Aviso>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1" checked={emitida} disabled={!verde} onChange={(e) => setEmitida(e.target.checked)} />
              <span>Confirmo que la certificación presupuestaria fue emitida *</span>
            </label>
            <AreaObservacion id="obs-certificacion" texto="Observación" valor={texto} onChange={setTexto}
              ayuda="Opcional para registrar; obligatoria para devolver o anular." />
            <div className="flex flex-wrap justify-end gap-3">
              <button type="button" className={`${peligro}`} disabled={!texto.trim()} onClick={() => setAccion("ANULADO")}>Anular por falta de disponibilidad</button>
              <button type="button" className={secundario} disabled={!texto.trim()} onClick={() => setAccion("DOCUMENTACION_VALIDADA")}>Devolver a Logística con observación</button>
              <button type="button" className={principal} disabled={!emitida || !verde} onClick={() => setAccion("CERTIFICADO")}>Registrar certificación emitida</button>
            </div>
          </section>
        )}
      </div>
      {accion && fila && (
        <Confirmacion titulo={{ CERTIFICADO: "¿Registrar la certificación emitida?", DOCUMENTACION_VALIDADA: "¿Devolver a Logística?", ANULADO: "¿Anular por falta de disponibilidad?" }[accion]}
          textoAccion={{ CERTIFICADO: "Registrar certificación", DOCUMENTACION_VALIDADA: "Devolver", ANULADO: "Anular" }[accion]}
          tipo={accion === "ANULADO" ? "peligro" : "principal"} ocupado={ocupado} onConfirmar={registrar} onCancelar={() => setAccion(null)}>
          <p>{{
            CERTIFICADO: <><strong>{fila.codigo}</strong> pasará a Certificado y a Logística para registrar la orden.</>,
            DOCUMENTACION_VALIDADA: <><strong>{fila.codigo}</strong> volverá a Logística para corregir el cuadro comparativo.</>,
            ANULADO: <><strong>{fila.codigo}</strong> se anulará y el trámite quedará cerrado.</>,
          }[accion]}</p>
          <p className="font-semibold">El cambio de estado no se puede deshacer.</p>
        </Confirmacion>
      )}
    </div>
  );
}
