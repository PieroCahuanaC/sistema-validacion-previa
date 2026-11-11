// P05. Aplicar ajuste sugerido (CU-05, RF-04; Figura 6 y Tabla 6 de la Práctica 7).
// Reformular cambia lo que se pide, no el precio de lo que ya se pidió: el precio de un ítem
// que se conserva queda bloqueado (RI-26). Reprogramar cambia la fecha de necesidad. Ninguna
// registra que el área rechazó las opciones; el requerimiento solo podrá anularse.
import { useEffect, useMemo, useState } from "react";
import { api, ErrorApi, type Detalle, type ItemAjuste } from "../lib/api";
import { formatoFecha, formatoSoles, hoyLima } from "../lib/formato";
import { Aviso, campo, Confirmacion, etiqueta, MOTIVO_CORTO, parametro, principal, secundario } from "./comunes";

const UNIDADES = ["unidad", "bolsa", "galón", "kilogramo", "metro", "metro lineal", "caja", "paquete", "día", "servicio", "saco"];
type Opcion = "REFORMULAR" | "REPROGRAMAR" | "NINGUNA";
type ItemDetalle = Detalle["items"][number];
type Fila = {
  original: ItemDetalle; modo: "conservar" | "reemplazar" | "quitar"; cantidad: string;
  nuevo: { descripcion: string; unidad_medida: string; cantidad: string; precio: string; fuente: "COTIZACION" | "COMPRA_ANTERIOR" };
};
const MENSAJE_RI26 = "El precio de un ítem que no cambia no se puede modificar (RI-26): bajarlo sin cambiar lo que se pide subvaluaría el requerimiento. Reduzca la cantidad o use «Reemplazar» para pedir un ítem distinto con su propio precio.";

const sumar = (filas: Fila[]) => filas.reduce((total, f) => {
  if (f.modo === "quitar") return total;
  if (f.modo === "reemplazar") return total + (Number(f.nuevo.cantidad) || 0) * (Number(f.nuevo.precio) || 0);
  return total + (Number(f.cantidad) || 0) * Number(f.original.precio_unitario_ref);
}, 0);

const diaSiguiente = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
};

export default function AjusteRequerimiento() {
  const id = Number(parametro("id"));
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [error, setError] = useState("");
  const [opcion, setOpcion] = useState<Opcion | null>(null);
  const [filas, setFilas] = useState<Fila[]>([]);
  const [fecha, setFecha] = useState("");
  const [bloqueo, setBloqueo] = useState<number | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    if (!id) { setError("Indique el requerimiento que desea ajustar."); return; }
    api.detalle(id).then((d) => {
      setDetalle(d);
      setFilas(d.items.map((i) => ({
        original: i, modo: "conservar", cantidad: String(Number(i.cantidad)),
        nuevo: { descripcion: "", unidad_medida: i.unidad_medida, cantidad: String(Number(i.cantidad)), precio: "", fuente: "COTIZACION" },
      })));
    }).catch((e: ErrorApi) => setError(e.message));
  }, [id]);

  const nuevoMonto = useMemo(() => sumar(filas), [filas]);
  const errores = useMemo(() => {
    const lista: string[] = [];
    if (opcion === "REFORMULAR") {
      const activas = filas.filter((f) => f.modo !== "quitar");
      if (!activas.length) lista.push("Debe quedar al menos un ítem.");
      filas.forEach((f, n) => {
        if (f.modo === "conservar") {
          const c = Number(f.cantidad);
          if (!(c > 0)) lista.push(`Ítem ${n + 1}: la cantidad debe ser mayor que 0.`);
          else if (c > Number(f.original.cantidad)) lista.push(`Ítem ${n + 1}: la cantidad solo puede reducirse (máximo ${Number(f.original.cantidad)}).`);
        }
        if (f.modo === "reemplazar" && (!f.nuevo.descripcion.trim() || !(Number(f.nuevo.cantidad) > 0) || !(Number(f.nuevo.precio) > 0))) {
          lista.push(`Ítem ${n + 1}: el ítem que lo reemplaza necesita descripción, cantidad y precio.`);
        }
      });
      const sinCambios = filas.every((f) => f.modo === "conservar" && Number(f.cantidad) === Number(f.original.cantidad));
      if (sinCambios) lista.push("Reduzca una cantidad, quite un ítem o reemplácelo.");
    }
    if (opcion === "REPROGRAMAR" && detalle && (!fecha || fecha <= detalle.fecha_necesidad || fecha < hoyLima())) {
      lista.push(`Elija una fecha posterior al ${formatoFecha(detalle.fecha_necesidad)}.`);
    }
    return lista;
  }, [opcion, filas, fecha, detalle]);

  const cambiar = (n: number, cambio: Partial<Fila>) => setFilas(filas.map((f, i) => i === n ? { ...f, ...cambio } : f));
  const cambiarNuevo = (n: number, cambio: Partial<Fila["nuevo"]>) =>
    setFilas(filas.map((f, i) => i === n ? { ...f, nuevo: { ...f.nuevo, ...cambio } } : f));

  async function aplicar() {
    if (!detalle || !opcion) return;
    setOcupado(true);
    try {
      let items: ItemAjuste[] | undefined;
      if (opcion === "REFORMULAR") {
        items = filas.filter((f) => f.modo !== "quitar").map((f) => f.modo === "conservar"
          ? { id_item_original: f.original.id_item, cantidad: f.cantidad }
          : { cantidad: f.nuevo.cantidad, descripcion: f.nuevo.descripcion.trim(), unidad_medida: f.nuevo.unidad_medida,
              precio_unitario_ref: Number(f.nuevo.precio).toFixed(2), fuente_precio: f.nuevo.fuente });
      }
      await api.aplicarAjuste(detalle.requerimiento_id, {
        opcion, items, fecha_necesidad_nueva: opcion === "REPROGRAMAR" ? fecha : undefined });
      window.location.href = `/requerimientos/detalle?id=${detalle.requerimiento_id}&ajustado=${opcion}`;
    } catch (e) {
      setError((e as ErrorApi).message);
      setConfirmar(false);
      setOcupado(false);
    }
  }

  if (!detalle) return error ? <Aviso tipo="error">{error}</Aviso> : <p className="text-pizarra">Cargando el requerimiento…</p>;
  if (!detalle.acciones.aplicar_ajuste) {
    return (
      <div className="max-w-3xl space-y-3">
        <Aviso tipo="info">El requerimiento {detalle.codigo} no admite un ajuste: solo se ajusta una vez la última validación en rojo de un requerimiento en Registrado.</Aviso>
        <a href={`/requerimientos/detalle?id=${detalle.requerimiento_id}`} className={`inline-block ${secundario}`}>Ver el requerimiento</a>
      </div>
    );
  }

  const b = detalle.semaforo.base_calculo;
  const diferencia = b.saldo_disponible === null ? null : Number(b.monto_evaluado) - Number(b.saldo_disponible);
  return (
    <div className="max-w-5xl space-y-4">
      {error && <Aviso tipo="error">{error}</Aviso>}
      <section aria-label="Resumen" className="rounded border border-rojo bg-rojo-suave p-4">
        <p className="font-semibold">{detalle.codigo} · {detalle.objeto_contratacion === "BIEN" ? "Bien" : "Servicio"} · Semáforo Rojo — {MOTIVO_CORTO[detalle.semaforo.motivo]}</p>
        <p className="mt-1 text-sm">{detalle.descripcion}</p>
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
          <div><dt className="text-pizarra">Monto evaluado</dt><dd className="cifra text-lg font-bold">{formatoSoles(b.monto_evaluado)}</dd></div>
          <div><dt className="text-pizarra">Saldo presupuestal disponible</dt><dd className="cifra text-lg font-bold">{formatoSoles(b.saldo_disponible)}</dd></div>
          <div><dt className="text-pizarra">Diferencia por cubrir</dt><dd className="cifra text-lg font-bold text-rojo">{formatoSoles(diferencia)}</dd></div>
        </dl>
        <p className="mt-2 text-xs">El saldo es crédito presupuestario aún no comprometido, no dinero en caja.</p>
      </section>

      <fieldset className="rounded border border-linea bg-superficie p-4">
        <legend className="px-1 font-semibold">Opción de ajuste *</legend>
        <div className="grid gap-3 md:grid-cols-3">
          {([
            ["REFORMULAR", "Reformular", "Reducir cantidades, quitar ítems o reemplazar un ítem por otro."],
            ["REPROGRAMAR", "Reprogramar", "Postergar la fecha de necesidad."],
            ["NINGUNA", "Ninguna", "No acepto ninguna opción; el requerimiento solo podrá anularse."],
          ] as const).map(([valor, titulo, ayuda]) => (
            <label key={valor} className={`cursor-pointer rounded border p-3 ${opcion === valor ? "border-accion bg-fondo" : "border-linea"}`}>
              <input type="radio" name="opcion" value={valor} checked={opcion === valor} onChange={() => setOpcion(valor)} className="mr-2" />
              <span className="font-semibold">{titulo}</span>
              <span className="mt-1 block text-xs text-pizarra">{ayuda}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {opcion === "REFORMULAR" && (
        <section aria-label="Ítems reformulados" className="rounded border border-linea bg-superficie p-4">
          <h2 className="font-semibold">Ítems del requerimiento</h2>
          <p className="mb-3 text-xs text-pizarra">Puede reducir la cantidad, quitar un ítem o reemplazarlo por otro de distinta especificación. El precio de un ítem que se conserva está bloqueado 🔒.</p>
          {bloqueo !== null && <div className="mb-3"><Aviso tipo="atencion">{MENSAJE_RI26}</Aviso></div>}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-fondo text-left">
                <tr><th className="p-2">Ítem</th><th className="p-2">Unidad</th><th className="p-2 text-right">Cantidad</th>
                  <th className="p-2 text-right">P. unit. ref.</th><th className="p-2 text-right">Subtotal</th><th className="p-2"><span className="sr-only">Acciones</span></th></tr>
              </thead>
              <tbody>
                {filas.map((f, n) => {
                  const nombre = `${n + 1}. ${f.original.descripcion}`;
                  if (f.modo === "reemplazar") {
                    return (
                      <tr key={f.original.id_item} className="border-b border-linea bg-fondo align-top">
                        <td className="p-2">
                          <span className="block text-xs text-pizarra line-through">{f.original.descripcion}</span>
                          <input aria-label={`Ítem que reemplaza a ${f.original.descripcion}`} className={campo} maxLength={250}
                            placeholder="Nuevo ítem (descripción y especificación)" value={f.nuevo.descripcion}
                            onChange={(e) => cambiarNuevo(n, { descripcion: e.target.value })} />
                        </td>
                        <td className="p-2">
                          <select aria-label="Unidad del ítem nuevo" className={campo} value={f.nuevo.unidad_medida}
                            onChange={(e) => cambiarNuevo(n, { unidad_medida: e.target.value })}>
                            {UNIDADES.map((u) => <option key={u}>{u}</option>)}
                          </select>
                        </td>
                        <td className="p-2"><input aria-label="Cantidad del ítem nuevo" type="number" min="0.01" step="0.01" className={`${campo} text-right`}
                          value={f.nuevo.cantidad} onChange={(e) => cambiarNuevo(n, { cantidad: e.target.value })} /></td>
                        <td className="p-2">
                          <input aria-label="Precio unitario del ítem nuevo" type="number" min="0.01" step="0.01" className={`${campo} text-right`}
                            value={f.nuevo.precio} onChange={(e) => cambiarNuevo(n, { precio: e.target.value })} />
                          <select aria-label="Fuente del precio" className={`${campo} mt-1 text-xs`} value={f.nuevo.fuente}
                            onChange={(e) => cambiarNuevo(n, { fuente: e.target.value as Fila["nuevo"]["fuente"] })}>
                            <option value="COTIZACION">Cotización</option><option value="COMPRA_ANTERIOR">Compra anterior</option>
                          </select>
                        </td>
                        <td className="cifra p-2 text-right">{formatoSoles((Number(f.nuevo.cantidad) || 0) * (Number(f.nuevo.precio) || 0))}</td>
                        <td className="p-2"><button type="button" className="text-sm font-semibold text-accion" onClick={() => cambiar(n, { modo: "conservar" })}>Deshacer</button></td>
                      </tr>
                    );
                  }
                  const quitado = f.modo === "quitar";
                  return (
                    <tr key={f.original.id_item} className={`border-b border-linea ${quitado ? "text-pizarra/60 line-through" : ""}`}>
                      <td className="p-2">{nombre}</td>
                      <td className="p-2">{f.original.unidad_medida}</td>
                      <td className="p-2 text-right">
                        {quitado ? Number(f.original.cantidad) : (
                          <input aria-label={`Cantidad de ${f.original.descripcion}`} type="number" min="0.01" step="0.01"
                            max={Number(f.original.cantidad)} className={`${campo} w-28 text-right`} value={f.cantidad}
                            onChange={(e) => cambiar(n, { cantidad: e.target.value })} />
                        )}
                      </td>
                      <td className="cifra p-2 text-right">
                        <button type="button" onClick={() => setBloqueo(n)} title="Precio bloqueado (RI-26)"
                          aria-label={`Precio de ${f.original.descripcion} bloqueado: ${formatoSoles(f.original.precio_unitario_ref)}`}
                          className="rounded px-1 hover:bg-fondo">🔒 {formatoSoles(f.original.precio_unitario_ref)}</button>
                      </td>
                      <td className="cifra p-2 text-right">{quitado ? "—" : formatoSoles((Number(f.cantidad) || 0) * Number(f.original.precio_unitario_ref))}</td>
                      <td className="p-2 whitespace-nowrap no-underline">
                        {quitado ? (
                          <button type="button" className="text-sm font-semibold text-accion" onClick={() => cambiar(n, { modo: "conservar" })}>Restaurar</button>
                        ) : (
                          <>
                            <button type="button" className="mr-2 text-sm font-semibold text-accion" onClick={() => cambiar(n, { modo: "reemplazar" })}>Reemplazar</button>
                            <button type="button" className="text-sm font-semibold text-rojo" onClick={() => cambiar(n, { modo: "quitar" })}>Quitar</button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr><td colSpan={4} className="p-2 text-right font-semibold">Nuevo monto estimado</td>
                  <td className="cifra p-2 text-right font-bold">{formatoSoles(nuevoMonto)}</td><td /></tr>
                {b.saldo_disponible !== null && (
                  <tr><td colSpan={6} className={`p-2 text-right text-xs ${nuevoMonto <= Number(b.saldo_disponible) ? "text-verde" : "text-rojo"}`}>
                    {nuevoMonto <= Number(b.saldo_disponible) ? "El nuevo monto está dentro del saldo presupuestal disponible." : `Aún supera el saldo disponible en ${formatoSoles(nuevoMonto - Number(b.saldo_disponible))}.`}
                  </td></tr>
                )}
              </tfoot>
            </table>
          </div>
        </section>
      )}

      {opcion === "REPROGRAMAR" && (
        <section className="rounded border border-linea bg-superficie p-4">
          <label htmlFor="fecha" className={etiqueta}>Nueva fecha de necesidad *</label>
          <input id="fecha" type="date" className={`${campo} max-w-xs`} value={fecha}
            min={diaSiguiente(detalle.fecha_necesidad > hoyLima() ? detalle.fecha_necesidad : hoyLima())}
            onChange={(e) => setFecha(e.target.value)} />
          <p className="mt-1 text-xs text-pizarra">Fecha actual de necesidad: {formatoFecha(detalle.fecha_necesidad)}. El sistema volverá a validar con el dato presupuestal vigente.</p>
        </section>
      )}

      {opcion === "NINGUNA" && (
        <Aviso tipo="atencion">Se registrará que el área rechazó todas las opciones. El requerimiento queda en Rojo sin más ajustes y solo podrá anularse desde el detalle (P04); la anulación lo cierra de forma definitiva.</Aviso>
      )}

      {opcion && errores.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-rojo" aria-live="polite">{errores.map((e) => <li key={e}>{e}</li>)}</ul>
      )}

      <div className="flex justify-end gap-3">
        <a href={`/requerimientos/detalle?id=${detalle.requerimiento_id}`} className={secundario}>Cancelar</a>
        <button type="button" className={principal} disabled={!opcion || errores.length > 0} onClick={() => setConfirmar(true)}>
          {opcion === "NINGUNA" ? "Registrar opción Ninguna" : "Aplicar ajuste y revalidar"}</button>
      </div>

      {confirmar && opcion && (
        <Confirmacion titulo={opcion === "NINGUNA" ? "¿Registrar que no acepta ningún ajuste?" : "¿Aplicar el ajuste y revalidar?"}
          textoAccion={opcion === "NINGUNA" ? "Registrar" : "Aplicar y revalidar"} ocupado={ocupado}
          onConfirmar={aplicar} onCancelar={() => setConfirmar(false)}>
          {opcion === "REFORMULAR" && <p>El monto estimado pasará de {formatoSoles(b.monto_evaluado)} a <strong>{formatoSoles(nuevoMonto)}</strong>. Luego deberá completar de nuevo el paso 2 y enviar el requerimiento.</p>}
          {opcion === "REPROGRAMAR" && <p>La fecha de necesidad pasará al <strong>{formatoFecha(fecha)}</strong>.</p>}
          <p className="font-semibold">Una vez registrado, el ajuste no se puede deshacer.</p>
        </Confirmacion>
      )}
    </div>
  );
}
