// P13. Registrar orden y compromiso SIAF (CU-14, RF-05, RF-07; Tabla 14 de la Práctica 7).
// La orden y el compromiso se registran fuera del sistema; aquí se confirma que ambos actos se
// realizaron y se cierra el trámite, con el tiempo hasta la certificación y el tiempo total.
import { useEffect, useState } from "react";
import { api, ErrorApi, type Historial } from "../lib/api";
import { formatoFechaHora, formatoSoles } from "../lib/formato";
import { AreaObservacion, Aviso, Confirmacion, horasTexto, principal } from "./comunes";
import { EnlacesExpediente, TablaExpedientes, useExpedientes } from "./ListaExpedientes";

export default function RegistrarOrden() {
  const { filas, fila, elegido, setElegido, cargar, error } = useExpedientes("CERTIFICADO");
  const [orden, setOrden] = useState(false);
  const [siaf, setSiaf] = useState(false);
  const [texto, setTexto] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [cerrado, setCerrado] = useState<Historial | null>(null);
  const [aviso, setAviso] = useState("");

  useEffect(() => { setOrden(false); setSiaf(false); setTexto(""); }, [elegido]);

  async function registrar() {
    if (!fila) return;
    setOcupado(true);
    try {
      await api.cambiarEtapa(fila.requerimiento_id, "ORDEN_EMITIDA", texto.trim());
      setCerrado(await api.historial(fila.requerimiento_id));
      setConfirmar(false);
      await cargar();
    } catch (e) {
      setAviso((e as ErrorApi).message);
      setConfirmar(false);
    } finally {
      setOcupado(false);
    }
  }

  const tipoOrden = fila?.objeto_contratacion === "SERVICIO" ? "orden de servicio" : "orden de compra";
  return (
    <div className="space-y-4">
      {cerrado && (
        <Aviso tipo="ok">
          <p className="font-semibold">{cerrado.codigo}: trámite cerrado con Orden emitida.</p>
          <p>Tiempo hasta la certificación: <strong>{horasTexto(cerrado.horas_hasta_certificacion)}</strong> · Tiempo total del trámite: <strong>{horasTexto(cerrado.horas_totales)}</strong>.</p>
          <a className="font-semibold underline" href={`/requerimientos/historial?id=${cerrado.requerimiento_id}`}>Ver el historial completo</a>
        </Aviso>
      )}
      {(aviso || error) && <Aviso tipo="error">{aviso || error}</Aviso>}
      <div className="grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <TablaExpedientes titulo="Certificados" filas={filas} elegido={elegido} onElegir={setElegido}
            vacio="No hay requerimientos certificados pendientes de orden." />
        </div>
        {fila && (
          <section aria-label={`Orden de ${fila.codigo}`} className="space-y-3 rounded border border-linea bg-superficie p-4 xl:col-span-3">
            <h2 className="text-lg font-bold">{fila.codigo}</h2>
            <p className="text-sm">{fila.descripcion}</p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt className="text-pizarra">Unidad y meta</dt><dd>{fila.unidad_sigla} · {fila.meta_codigo}</dd>
              <dt className="text-pizarra">Monto estimado</dt><dd className="cifra">{formatoSoles(fila.monto_estimado)}</dd>
              <dt className="text-pizarra">Certificado el</dt><dd>{formatoFechaHora(fila.desde)}</dd>
              <dt className="text-pizarra">Tipo de orden</dt><dd className="capitalize">{tipoOrden}</dd>
            </dl>
            <EnlacesExpediente id={fila.requerimiento_id} />
            <Aviso tipo="info">La {tipoOrden} y el compromiso se registran fuera del sistema (SIAF). Aquí se confirma que ambos se realizaron.</Aviso>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={orden} onChange={(e) => setOrden(e.target.checked)} />
              <span>La {tipoOrden} fue emitida *</span></label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={siaf} onChange={(e) => setSiaf(e.target.checked)} />
              <span>El compromiso fue registrado en el SIAF *</span></label>
            <AreaObservacion id="obs-orden" texto="Observación (opcional)" valor={texto} onChange={setTexto} ayuda="Por ejemplo, el número de la orden." />
            <div className="flex justify-end">
              <button type="button" className={principal} disabled={!orden || !siaf} onClick={() => setConfirmar(true)}>Registrar y cerrar trámite</button>
            </div>
          </section>
        )}
      </div>
      {confirmar && fila && (
        <Confirmacion titulo="¿Registrar la orden y cerrar el trámite?" textoAccion="Registrar y cerrar" ocupado={ocupado}
          onConfirmar={registrar} onCancelar={() => setConfirmar(false)}>
          <p><strong>{fila.codigo}</strong> pasará a Orden emitida y se detendrá el cómputo del tiempo.</p>
          <p className="font-semibold">El trámite quedará cerrado y no se puede deshacer.</p>
        </Confirmacion>
      )}
    </div>
  );
}
