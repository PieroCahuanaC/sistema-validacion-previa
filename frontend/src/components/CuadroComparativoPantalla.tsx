// P10. Cuadro comparativo (CU-08, RF-12; Figura 11 y Tabla 11 de la Práctica 7).
// Proveedor por RUC (o registrado en el momento), monto y fecha por cotización; precio de
// referencia con su criterio; modo corrección cuando Presupuesto devuelve el expediente.
// Si el precio supera el monto validado, el sistema vuelve a validar el semáforo (estado E).
import { useEffect, useMemo, useState } from "react";
import { api, ErrorApi, type CotizacionEntrada, type Cuadro } from "../lib/api";
import { formatoSoles, hoyLima } from "../lib/formato";
import { AreaObservacion, Aviso, campo, Confirmacion, etiqueta, principal, secundario } from "./comunes";
import { EnlacesExpediente, TablaExpedientes, useExpedientes } from "./ListaExpedientes";

type Fila = {
  clave: number; ruc: string; estado: "buscar" | "encontrado" | "nuevo"; id_proveedor?: number;
  tipo: "NATURAL" | "JURIDICA"; razon: string; monto: string; fecha: string; mensaje?: string;
};
let siguiente = 1;
const vacia = (): Fila => ({ clave: siguiente++, ruc: "", estado: "buscar", tipo: "JURIDICA", razon: "", monto: "", fecha: "" });

export default function CuadroComparativoPantalla() {
  const { filas: expedientes, fila, elegido, setElegido, cargar, error } = useExpedientes("DOCUMENTACION_VALIDADA");
  const [cuadro, setCuadro] = useState<Cuadro | null>(null);
  const [filas, setFilas] = useState<Fila[]>([vacia()]);
  const [precio, setPrecio] = useState("");
  const [observacion, setObservacion] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error" | "atencion"; texto: string } | null>(null);

  useEffect(() => {
    if (!elegido) return;
    api.cuadro(elegido).then((c) => {
      setCuadro(c);
      setPrecio(c.precio_referencia ? Number(c.precio_referencia).toFixed(2) : "");
      setObservacion(c.observacion ?? "");
      setFilas(c.cotizaciones.length ? c.cotizaciones.map((q) => ({
        clave: siguiente++, ruc: q.proveedor?.ruc ?? "", estado: "encontrado", id_proveedor: q.proveedor?.id_proveedor,
        tipo: q.proveedor?.tipo_persona ?? "JURIDICA", razon: q.proveedor?.razon_social ?? "",
        monto: Number(q.monto).toFixed(2), fecha: q.fecha_cotizacion })) : [vacia()]);
    }).catch((e: ErrorApi) => setAviso({ tipo: "error", texto: e.message }));
  }, [elegido]);

  const montos = filas.map((f) => Number(f.monto)).filter((m) => m > 0);
  const menor = montos.length ? Math.min(...montos) : null;
  const promedio = montos.length ? montos.reduce((a, b) => a + b, 0) / montos.length : null;
  const validado = cuadro ? Number(cuadro.monto_validado) : 0;
  const supera = Number(precio) > validado;
  const errores = useMemo(() => {
    const lista: string[] = [];
    filas.forEach((f, n) => {
      if (f.estado === "buscar") lista.push(`Cotización ${n + 1}: busque el proveedor por su RUC.`);
      if (f.estado === "nuevo" && f.razon.trim().length < 2) lista.push(`Cotización ${n + 1}: indique la razón social o el nombre.`);
      if (!(Number(f.monto) > 0)) lista.push(`Cotización ${n + 1}: el monto debe ser mayor que 0.`);
      if (!f.fecha) lista.push(`Cotización ${n + 1}: indique la fecha de la cotización.`);
    });
    const rucs = filas.map((f) => f.ruc).filter(Boolean);
    if (new Set(rucs).size !== rucs.length) lista.push("Un proveedor solo puede cotizar una vez en el cuadro.");
    if (!(Number(precio) > 0)) lista.push("Indique el precio de referencia.");
    return lista;
  }, [filas, precio]);

  const cambiar = (clave: number, cambio: Partial<Fila>) => setFilas(filas.map((f) => (f.clave === clave ? { ...f, ...cambio } : f)));

  async function buscar(f: Fila) {
    if (!/^\d{11}$/.test(f.ruc)) { cambiar(f.clave, { mensaje: "El RUC tiene 11 dígitos." }); return; }
    try {
      const r = await api.buscarProveedor(f.ruc);
      if (r.encontrado && r.proveedor) {
        cambiar(f.clave, { estado: "encontrado", id_proveedor: r.proveedor.id_proveedor, tipo: r.proveedor.tipo_persona,
          razon: r.proveedor.razon_social, mensaje: undefined });
      } else {
        cambiar(f.clave, { estado: "nuevo", id_proveedor: undefined, tipo: f.ruc.startsWith("20") ? "JURIDICA" : "NATURAL", razon: "",
          mensaje: "Proveedor nuevo: complete sus datos." });
      }
    } catch (e) {
      cambiar(f.clave, { mensaje: (e as ErrorApi).message });
    }
  }

  async function guardar() {
    if (!fila) return;
    setOcupado(true);
    try {
      const cotizaciones: CotizacionEntrada[] = filas.map((f) => ({
        ...(f.estado === "encontrado" && f.id_proveedor ? { id_proveedor: f.id_proveedor }
          : { proveedor: { tipo_persona: f.tipo, ruc: f.ruc, razon_social: f.razon.trim() } }),
        monto: Number(f.monto).toFixed(2), fecha_cotizacion: f.fecha }));
      const r = await api.guardarCuadro(fila.requerimiento_id, { cotizaciones, precio_referencia: Number(precio).toFixed(2),
        observacion: observacion.trim() || null });
      setAviso(r.destino === "PRESUPUESTO"
        ? { tipo: r.semaforo_vigente === "VERDE" ? "ok" : "atencion", texto: `${r.codigo}: cuadro ${r.modo === "CORRECCION" ? "corregido" : "registrado"}; el expediente pasó a Presupuesto para la certificación.${r.revalidado ? ` Se revalidó con el precio de mercado: semáforo ${r.estado_semaforo === "VERDE" ? "verde" : "ámbar (Presupuesto decidirá en su Panel de alertas)"}.` : ""}` }
        : { tipo: "atencion", texto: `${r.codigo}: con el precio de mercado el semáforo quedó en ROJO. El expediente volvió al Área Usuaria para que ajuste el requerimiento.` });
      setConfirmar(false);
      setCuadro(null);
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
      {(aviso || error) && <Aviso tipo={aviso?.tipo ?? "error"}>{aviso?.texto ?? error}</Aviso>}
      <div className="grid gap-4 2xl:grid-cols-5">
        <div className="2xl:col-span-2">
          <TablaExpedientes titulo="Por elaborar o corregir" filas={expedientes} elegido={elegido} onElegir={setElegido}
            vacio="No hay expedientes con documentación validada pendientes de cuadro." />
        </div>
        {fila && cuadro && cuadro.requerimiento_id === fila.requerimiento_id && (
          <section aria-label={`Cuadro de ${fila.codigo}`} className="space-y-4 rounded border border-linea bg-superficie p-4 2xl:col-span-3">
            <div>
              <h2 className="text-lg font-bold">{fila.codigo} {cuadro.modo === "CORRECCION" && <span className="ml-2 rounded bg-ambar-suave px-2 py-0.5 text-xs text-ambar">Modo corrección</span>}</h2>
              <p className="text-sm">{fila.descripcion}</p>
              <p className="text-sm text-pizarra">{fila.unidad_sigla} · Meta {fila.meta_codigo} · Monto estimado {formatoSoles(fila.monto_estimado)} · Monto validado {formatoSoles(cuadro.monto_validado)}</p>
              <EnlacesExpediente id={fila.requerimiento_id} />
            </div>
            {cuadro.devolucion_presupuesto && <Aviso tipo="atencion"><strong>Devuelto por Presupuesto:</strong> {cuadro.devolucion_presupuesto}</Aviso>}

            <div className="space-y-3">
              <h3 className="font-semibold">Cotizaciones *</h3>
              {filas.map((f, n) => (
                <fieldset key={f.clave} className="rounded border border-linea p-3">
                  <legend className="px-1 text-sm font-semibold">Cotización {n + 1}</legend>
                  <div className="grid gap-3 md:grid-cols-12">
                    <div className="md:col-span-5">
                      <label htmlFor={`ruc-${f.clave}`} className={etiqueta}>RUC del proveedor *</label>
                      <div className="flex gap-2">
                        <input id={`ruc-${f.clave}`} inputMode="numeric" maxLength={11} className={campo} value={f.ruc}
                          onChange={(e) => cambiar(f.clave, { ruc: e.target.value.replace(/\D/g, ""), estado: "buscar", id_proveedor: undefined, mensaje: undefined })} />
                        <button type="button" className={`${secundario} px-3`} onClick={() => buscar(f)}>Buscar</button>
                      </div>
                      {f.mensaje && <p className="mt-1 text-xs text-pizarra">{f.mensaje}</p>}
                    </div>
                    <div className="md:col-span-4">
                      {f.estado === "encontrado" && (
                        <><span className={etiqueta}>Proveedor</span>
                          <p className="py-2 text-sm">{f.razon} <span className="text-xs text-pizarra">({f.tipo === "NATURAL" ? "persona natural" : "persona jurídica"})</span></p></>
                      )}
                      {f.estado === "nuevo" && (
                        <>
                          <span className={etiqueta}>Tipo de persona *</span>
                          <label className="mr-3 text-sm"><input type="radio" className="mr-1" checked={f.tipo === "JURIDICA"} onChange={() => cambiar(f.clave, { tipo: "JURIDICA" })} />Jurídica</label>
                          <label className="text-sm"><input type="radio" className="mr-1" checked={f.tipo === "NATURAL"} onChange={() => cambiar(f.clave, { tipo: "NATURAL" })} />Natural</label>
                          <input aria-label="Razón social o nombre" maxLength={300} className={`${campo} mt-1`} placeholder="Razón social o nombre *"
                            value={f.razon} onChange={(e) => cambiar(f.clave, { razon: e.target.value })} />
                          {f.tipo === "NATURAL" && <p className="mt-1 text-xs text-pizarra">Dato personal: el RUC y el nombre se guardan cifrados.</p>}
                        </>
                      )}
                    </div>
                    <div className="md:col-span-3 space-y-2">
                      <div>
                        <label htmlFor={`monto-${f.clave}`} className={etiqueta}>Monto (S/) *</label>
                        <input id={`monto-${f.clave}`} type="number" min="0.01" step="0.01" className={`${campo} text-right`} value={f.monto}
                          onChange={(e) => cambiar(f.clave, { monto: e.target.value })} />
                      </div>
                      <div>
                        <label htmlFor={`fecha-${f.clave}`} className={etiqueta}>Fecha de cotización *</label>
                        <input id={`fecha-${f.clave}`} type="date" max={hoyLima()} className={campo} value={f.fecha}
                          onChange={(e) => cambiar(f.clave, { fecha: e.target.value })} />
                      </div>
                    </div>
                  </div>
                  {filas.length > 1 && (
                    <button type="button" className="mt-2 text-sm font-semibold text-rojo" onClick={() => setFilas(filas.filter((x) => x.clave !== f.clave))}>Quitar cotización</button>
                  )}
                </fieldset>
              ))}
              <button type="button" className={secundario} onClick={() => setFilas([...filas, vacia()])}>+ Agregar cotización</button>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded bg-fondo p-3 text-sm"><span className="text-pizarra">Menor cotización</span>
                <span className="cifra block text-lg font-bold">{formatoSoles(menor)}</span>
                {menor !== null && <button type="button" className="text-xs font-semibold text-accion" onClick={() => setPrecio(menor.toFixed(2))}>Usar como precio de referencia</button>}</div>
              <div className="rounded bg-fondo p-3 text-sm"><span className="text-pizarra">Promedio</span>
                <span className="cifra block text-lg font-bold">{formatoSoles(promedio)}</span></div>
              <div>
                <label htmlFor="precio" className={etiqueta}>Precio de referencia (S/) *</label>
                <input id="precio" type="number" min="0.01" step="0.01" className={`${campo} text-right`} value={precio} onChange={(e) => setPrecio(e.target.value)} />
              </div>
            </div>
            {Number(precio) > 0 && supera && (
              <Aviso tipo="atencion">El precio de referencia supera el monto validado ({formatoSoles(validado)}): al registrar, el sistema volverá a validar el semáforo con este precio. Si el saldo no lo cubre, el expediente volverá al Área Usuaria para ajustarlo.</Aviso>
            )}
            <AreaObservacion id="criterio" texto="Observación o criterio" valor={observacion} onChange={setObservacion} ayuda="Por ejemplo, por qué se eligió ese precio." />

            {errores.length > 0 && <ul className="list-disc pl-5 text-sm text-rojo" aria-live="polite">{errores.map((e) => <li key={e}>{e}</li>)}</ul>}
            <div className="flex justify-end">
              <button type="button" className={principal} disabled={errores.length > 0} onClick={() => setConfirmar(true)}>
                {cuadro.modo === "CORRECCION" ? "Guardar corrección del cuadro" : "Registrar cuadro comparativo"}</button>
            </div>
          </section>
        )}
      </div>
      {confirmar && fila && (
        <Confirmacion titulo={cuadro?.modo === "CORRECCION" ? "¿Guardar la corrección del cuadro?" : "¿Registrar el cuadro comparativo?"}
          textoAccion="Registrar" ocupado={ocupado} onConfirmar={guardar} onCancelar={() => setConfirmar(false)}>
          <p>{filas.length} cotización(es) y precio de referencia de <strong>{formatoSoles(Number(precio))}</strong> para {fila.codigo}.</p>
          <p>{supera ? "El sistema revalidará el semáforo con este precio antes de enviarlo a Presupuesto." : "El expediente pasará a Presupuesto para la certificación."}</p>
        </Confirmacion>
      )}
    </div>
  );
}
