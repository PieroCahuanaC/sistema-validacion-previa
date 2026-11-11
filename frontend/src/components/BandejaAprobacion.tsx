// P08. Bandeja de aprobación de la Gerencia de Administración (CU-11, RF-13; Tabla 9 de la
// Práctica 7). Solo llegan requerimientos enviados con semáforo vigente verde (RI-20).
import { useEffect, useState } from "react";
import { api, ErrorApi, type FilaBandeja } from "../lib/api";
import { formatoFecha, formatoFechaHora, formatoSoles } from "../lib/formato";
import {
  AreaObservacion, Aviso, Confirmacion, horasTexto, MOTIVO_CORTO, parametro, principal, secundario, Semaforo,
} from "./comunes";

export default function BandejaAprobacion() {
  const [filas, setFilas] = useState<FilaBandeja[] | null>(null);
  const [elegido, setElegido] = useState<number | null>(Number(parametro("id")) || null);
  const [texto, setTexto] = useState("");
  const [accion, setAccion] = useState<"APROBADO" | "OBSERVADO" | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  const cargar = () => api.bandeja().then((f) => {
    setFilas(f);
    setElegido((actual) => (actual && f.some((x) => x.requerimiento_id === actual) ? actual : f[0]?.requerimiento_id ?? null));
  }).catch((e: ErrorApi) => setAviso({ tipo: "error", texto: e.message }));
  useEffect(() => { cargar(); }, []);

  const fila = filas?.find((f) => f.requerimiento_id === elegido) ?? null;

  async function registrar() {
    if (!fila || !accion) return;
    setOcupado(true);
    try {
      await api.cambiarEtapa(fila.requerimiento_id, accion, texto);
      setAviso({ tipo: "ok", texto: accion === "APROBADO"
        ? `${fila.codigo} aprobado y derivado a Abastecimientos.`
        : `${fila.codigo} observado y devuelto al Área Usuaria.` });
      setTexto(""); setAccion(null); setElegido(null);
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
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
      {filas === null ? <p className="text-pizarra">Cargando la bandeja…</p> : filas.length === 0 ? (
        <p className="rounded border border-linea bg-superficie p-4 text-pizarra">No hay requerimientos por aprobar.</p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-5">
          <section aria-label="Por aprobar" className="overflow-x-auto rounded border border-linea bg-superficie xl:col-span-3">
            <table className="w-full text-left text-sm">
              <caption className="p-3 text-left font-semibold">Por aprobar ({filas.length})</caption>
              <thead className="bg-fondo text-pizarra">
                <tr><th scope="col" className="px-3 py-2">Código</th><th scope="col" className="px-3 py-2">Unidad</th>
                  <th scope="col" className="px-3 py-2">Meta</th><th scope="col" className="px-3 py-2">Objeto</th>
                  <th scope="col" className="px-3 py-2 text-right">Monto</th><th scope="col" className="px-3 py-2">Semáforo</th>
                  <th scope="col" className="px-3 py-2">En bandeja / plazo</th></tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={f.requerimiento_id} onClick={() => setElegido(f.requerimiento_id)}
                    className={`cursor-pointer border-t border-linea ${f.requerimiento_id === elegido ? "bg-fondo" : "hover:bg-fondo/60"}`}>
                    <td className="px-3 py-2 font-semibold whitespace-nowrap">
                      <button type="button" className="underline-offset-2 hover:underline" aria-pressed={f.requerimiento_id === elegido}
                        onClick={() => setElegido(f.requerimiento_id)}>{f.codigo}</button>
                    </td>
                    <td className="px-3 py-2">{f.unidad_sigla}</td>
                    <td className="px-3 py-2">{f.meta_codigo}</td>
                    <td className="px-3 py-2">{f.objeto_contratacion === "BIEN" ? "Bien" : "Servicio"}</td>
                    <td className="cifra px-3 py-2 text-right">{formatoSoles(f.monto_estimado)}</td>
                    <td className="px-3 py-2"><Semaforo vigente="VERDE" confirmado={f.confirmado_por_presupuesto} /></td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {horasTexto(f.horas_en_bandeja)} / {horasTexto(f.plazo_horas)}
                      {f.excedido && <span className="ml-2 rounded bg-rojo-suave px-1.5 py-0.5 text-xs font-semibold text-rojo">Excedido</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {fila && (
            <section aria-label={`Detalle de ${fila.codigo}`} className="space-y-3 rounded border border-linea bg-superficie p-4 xl:col-span-2">
              <h2 className="text-lg font-bold">{fila.codigo}</h2>
              <p className="text-sm">{fila.descripcion}</p>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <dt className="text-pizarra">Unidad</dt><dd>{fila.unidad_nombre}</dd>
                <dt className="text-pizarra">Meta</dt><dd>{fila.meta_codigo} · {fila.meta_nombre}</dd>
                <dt className="text-pizarra">Monto estimado</dt><dd className="cifra font-semibold">{formatoSoles(fila.monto_estimado)}</dd>
                <dt className="text-pizarra">Fecha de necesidad</dt><dd>{formatoFecha(fila.fecha_necesidad)}</dd>
                <dt className="text-pizarra">Enviado</dt><dd>{formatoFechaHora(fila.fecha_envio)}</dd>
              </dl>
              <div className="rounded border border-verde bg-verde-suave p-2 text-sm">
                <Semaforo vigente="VERDE" confirmado={fila.confirmado_por_presupuesto} />
                <span className="ml-2">{MOTIVO_CORTO[fila.motivo] ?? fila.motivo} · validado el {formatoFechaHora(fila.fecha_validacion)}</span>
              </div>
              <p className="text-sm">
                <a className="font-semibold text-accion hover:underline" href={`/requerimientos/detalle?id=${fila.requerimiento_id}`}>Ver detalle completo</a>
                {" · "}
                <a className="font-semibold text-accion hover:underline" href={`/requerimientos/historial?id=${fila.requerimiento_id}`}>Ver historial</a>
              </p>
              <AreaObservacion id="proveido" texto="Proveído u observación" valor={texto} onChange={setTexto}
                ayuda="Obligatorio para observar; opcional para aprobar." />
              <div className="flex flex-wrap justify-end gap-3">
                <button type="button" className={secundario} disabled={!texto.trim()} onClick={() => setAccion("OBSERVADO")}
                  title={texto.trim() ? undefined : "Escriba la observación para devolver"}>Observar y devolver</button>
                <button type="button" className={principal} onClick={() => setAccion("APROBADO")}>Aprobar y derivar a Abastecimientos</button>
              </div>
            </section>
          )}
        </div>
      )}

      {accion && fila && (
        <Confirmacion titulo={accion === "APROBADO" ? "¿Aprobar el requerimiento?" : "¿Observar y devolver?"}
          textoAccion={accion === "APROBADO" ? "Aprobar y derivar" : "Observar y devolver"} ocupado={ocupado}
          onConfirmar={registrar} onCancelar={() => setAccion(null)}>
          <p>{accion === "APROBADO"
            ? <>Se aprobará <strong>{fila.codigo}</strong> y pasará al Jefe de Logística y Abastecimientos para la validación documental.</>
            : <>Se devolverá <strong>{fila.codigo}</strong> al Área Usuaria con su observación.</>}</p>
          {texto.trim() && <p className="rounded bg-fondo p-2">{texto.trim()}</p>}
          <p className="font-semibold">El cambio de estado no se puede deshacer.</p>
        </Confirmacion>
      )}
    </div>
  );
}
