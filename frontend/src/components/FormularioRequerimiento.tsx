// P03. Registrar requerimiento (CU-03, RF-01). Al registrar, el sistema ejecuta la validación
// presupuestal (CU-01) y abre la P04 con el resultado.
// Hallazgo H2 de la prueba de usabilidad: los campos son editables y "Registrar y validar" solo
// se habilita cuando los campos obligatorios son válidos (Tabla 4 de la Práctica 7).
import { useEffect, useMemo, useState } from "react";
import { api, ErrorApi, type ItemEntrada, type Meta, type PacItem } from "../lib/api";
import { formatoFecha, formatoSoles, hoyLima } from "../lib/formato";

const UNIDADES = ["unidad", "bolsa", "galón", "kilogramo", "metro", "metro lineal", "caja", "paquete", "día", "servicio"];
const itemVacio = (): ItemEntrada => ({
  descripcion: "", unidad_medida: "unidad", cantidad: "", precio_unitario_ref: "", fuente_precio: "COTIZACION",
});
const subtotal = (i: ItemEntrada) => (Number(i.cantidad) || 0) * (Number(i.precio_unitario_ref) || 0);
const itemCompleto = (i: ItemEntrada) =>
  i.descripcion.trim() !== "" && Number(i.cantidad) > 0 && Number(i.precio_unitario_ref) > 0;

const campo = "w-full rounded border border-linea bg-white px-3 py-2 disabled:bg-fondo";
const etiqueta = "mb-1 block text-sm font-semibold";

export default function FormularioRequerimiento() {
  const [metas, setMetas] = useState<Meta[]>([]);
  const [pac, setPac] = useState<PacItem[]>([]);
  const [tope, setTope] = useState<number | null>(null);
  const [errorCarga, setErrorCarga] = useState("");

  const [metaCodigo, setMetaCodigo] = useState("");
  const [objeto, setObjeto] = useState<"BIEN" | "SERVICIO" | "">("");
  const [descripcion, setDescripcion] = useState("");
  const [items, setItems] = useState<ItemEntrada[]>([itemVacio()]);
  const [pacRef, setPacRef] = useState("");
  const [noPrevisto, setNoPrevisto] = useState(false);
  const [fecha, setFecha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState<ErrorApi | null>(null);

  useEffect(() => {
    Promise.all([api.metas(), api.pac(), api.regla()])
      .then(([m, p, r]) => { setMetas(m); setPac(p); setTope(Number(r.tope_8_uit)); })
      .catch((e: ErrorApi) => setErrorCarga(e.message));
  }, []);

  const meta = metas.find((m) => m.codigo === metaCodigo);
  const monto = useMemo(() => Math.round(items.reduce((s, i) => s + subtotal(i), 0) * 100) / 100, [items]);
  const superaTope = tope !== null && monto > tope;
  const hayItemIncompleto = items.some((i) => !itemCompleto(i));
  const valido = metaCodigo !== "" && objeto !== "" && descripcion.trim() !== "" && items.length > 0 &&
    !hayItemIncompleto && monto > 0 && !superaTope && fecha !== "" && fecha >= hoyLima() &&
    (noPrevisto || pacRef !== "");

  const cambiarItem = (n: number, cambios: Partial<ItemEntrada>) =>
    setItems((lista) => lista.map((i, k) => (k === n ? { ...i, ...cambios } : i)));

  async function registrar(e: React.FormEvent) {
    e.preventDefault();
    if (!valido || objeto === "") return;
    setEnviando(true);
    setErrorEnvio(null);
    try {
      const r = await api.registrar({
        meta_codigo: metaCodigo, objeto_contratacion: objeto, descripcion: descripcion.trim(),
        items: items.map((i) => ({ ...i, descripcion: i.descripcion.trim() })),
        fecha_necesidad: fecha, pac_item_referencia: noPrevisto ? null : pacRef,
      });
      window.location.href = `/requerimientos/detalle?id=${r.requerimiento_id}&registrado=1`;
    } catch (err) {
      setErrorEnvio(err as ErrorApi);
      setEnviando(false);
    }
  }

  if (errorCarga) {
    return <p role="alert" className="rounded border border-rojo bg-rojo-suave p-3">{errorCarga}</p>;
  }

  return (
    <form onSubmit={registrar} className="max-w-5xl space-y-5 rounded border border-linea bg-superficie p-5">
      {errorEnvio && (
        <div role="alert" className="rounded border border-rojo bg-rojo-suave p-3 text-sm">
          <p className="font-semibold">{errorEnvio.message}</p>
          {errorEnvio.errores.length > 0 && (
            <ul className="mt-1 list-disc pl-5">{errorEnvio.errores.map((x) => <li key={x.campo}>{x.campo}: {x.mensaje}</li>)}</ul>
          )}
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <label htmlFor="meta" className={etiqueta}>Meta presupuestal *</label>
          <select id="meta" className={campo} value={metaCodigo} onChange={(e) => setMetaCodigo(e.target.value)}>
            <option value="">Seleccione la meta</option>
            {metas.map((m) => <option key={m.codigo} value={m.codigo}>{m.codigo} · {m.nombre}</option>)}
          </select>
          {meta && (
            <p className="mt-2 rounded bg-fondo p-2 text-sm">
              Saldo presupuestal disponible referencial:{" "}
              <strong className="cifra">{meta.saldo_disponible === null ? "sin datos en la base local" : formatoSoles(meta.saldo_disponible)}</strong>
              {meta.fecha_corte && <> al {formatoFecha(meta.fecha_corte)}</>}.
              <span className="block text-pizarra">Es crédito presupuestario aún no comprometido, no dinero en caja.</span>
            </p>
          )}
        </div>
        <fieldset>
          <legend className={etiqueta}>Objeto de contratación *</legend>
          <div className="flex gap-6 pt-2">
            {(["BIEN", "SERVICIO"] as const).map((o) => (
              <label key={o} className="flex items-center gap-2">
                <input type="radio" name="objeto" checked={objeto === o} onChange={() => setObjeto(o)} />
                {o === "BIEN" ? "Bien" : "Servicio"}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <div>
        <label htmlFor="descripcion" className={etiqueta}>Descripción general *</label>
        <textarea id="descripcion" className={campo} rows={2} maxLength={500} value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)} />
        <p className="mt-1 flex justify-between text-xs text-pizarra">
          <span>Describa la necesidad. No escriba nombres de personas.</span><span>{descripcion.length}/500</span>
        </p>
      </div>

      <div>
        <p className={etiqueta}>Ítems del requerimiento *</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-fondo text-left">
              <tr>
                <th className="p-2">Ítem (descripción y especificación)</th><th className="p-2">Unidad</th>
                <th className="p-2">Cantidad</th><th className="p-2">P. unit. ref. (S/)</th>
                <th className="p-2">Fuente del precio</th><th className="p-2 text-right">Subtotal</th><th className="p-2" />
              </tr>
            </thead>
            <tbody>
              {items.map((i, n) => (
                <tr key={n} className="border-b border-linea align-top">
                  <td className="p-1 min-w-56">
                    <input aria-label={`Descripción del ítem ${n + 1}`} className={campo} maxLength={250}
                      value={i.descripcion} onChange={(e) => cambiarItem(n, { descripcion: e.target.value })} />
                  </td>
                  <td className="p-1">
                    <select aria-label={`Unidad del ítem ${n + 1}`} className={campo} value={i.unidad_medida}
                      onChange={(e) => cambiarItem(n, { unidad_medida: e.target.value })}>
                      {UNIDADES.map((u) => <option key={u}>{u}</option>)}
                    </select>
                  </td>
                  <td className="p-1 w-28">
                    <input aria-label={`Cantidad del ítem ${n + 1}`} className={`${campo} cifra`} type="number" min="0.01" step="0.01"
                      value={i.cantidad} onChange={(e) => cambiarItem(n, { cantidad: e.target.value })} />
                  </td>
                  <td className="p-1 w-32">
                    <input aria-label={`Precio unitario del ítem ${n + 1}`} className={`${campo} cifra`} type="number" min="0.01" step="0.01"
                      value={i.precio_unitario_ref} onChange={(e) => cambiarItem(n, { precio_unitario_ref: e.target.value })} />
                  </td>
                  <td className="p-1">
                    <select aria-label={`Fuente del precio del ítem ${n + 1}`} className={campo} value={i.fuente_precio}
                      onChange={(e) => cambiarItem(n, { fuente_precio: e.target.value as ItemEntrada["fuente_precio"] })}>
                      <option value="COTIZACION">Cotización</option>
                      <option value="COMPRA_ANTERIOR">Compra anterior</option>
                    </select>
                  </td>
                  <td className="cifra p-2 text-right">{formatoSoles(subtotal(i))}</td>
                  <td className="p-1">
                    <button type="button" disabled={items.length === 1} onClick={() => setItems(items.filter((_, k) => k !== n))}
                      className="rounded px-2 py-2 text-rojo hover:bg-rojo-suave disabled:opacity-30">Quitar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <button type="button" onClick={() => setItems([...items, itemVacio()])}
            className="rounded border border-accion px-3 py-1.5 text-sm text-accion hover:bg-fondo">Agregar ítem</button>
          <div className="text-right">
            <p className="text-sm">Monto estimado (suma de los ítems)</p>
            <p className={`cifra text-xl font-bold ${superaTope ? "text-rojo" : ""}`}>{formatoSoles(monto)}</p>
          </div>
        </div>
        {hayItemIncompleto && items.some((i) => i.descripcion || i.cantidad || i.precio_unitario_ref) && (
          <p className="mt-2 text-sm text-rojo">Complete la descripción, la cantidad y el precio de cada ítem.</p>
        )}
        {superaTope && (
          <p role="alert" className="mt-2 text-sm text-rojo">
            El monto supera el tope de 8 UIT ({formatoSoles(tope)}). Reduzca las cantidades o los ítems.
          </p>
        )}
        <p className="mt-1 text-xs text-pizarra">
          El monto no puede superar 8 UIT{tope !== null && <> ({formatoSoles(tope)})</>}. El precio debe corresponder al mercado.
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <label htmlFor="pac" className={etiqueta}>Ítem del PAC</label>
          <select id="pac" className={campo} value={pacRef} disabled={noPrevisto} onChange={(e) => setPacRef(e.target.value)}>
            <option value="">Seleccione el ítem del PAC</option>
            {pac.map((p) => <option key={p.numero_referencia} value={p.numero_referencia}>{p.numero_referencia} · {p.descripcion}</option>)}
          </select>
          <label className="mt-2 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={noPrevisto} onChange={(e) => { setNoPrevisto(e.target.checked); setPacRef(""); }} />
            No está previsto en el PAC
          </label>
          {noPrevisto && (
            <p className="mt-1 rounded bg-ambar-suave p-2 text-sm">
              Un requerimiento no previsto en el PAC queda en ámbar y el Jefe de Presupuesto confirmará la disponibilidad.
            </p>
          )}
        </div>
        <div>
          <label htmlFor="fecha" className={etiqueta}>Fecha de necesidad *</label>
          <input id="fecha" type="date" className={campo} min={hoyLima()} value={fecha} onChange={(e) => setFecha(e.target.value)} />
          <p className="mt-1 text-xs text-pizarra">Fecha en que el área necesita el bien o servicio. No puede ser anterior a hoy.</p>
        </div>
      </div>

      <div className="flex justify-end gap-3 border-t border-linea pt-4">
        <a href="/requerimientos/nuevo" className="rounded border border-linea px-4 py-2 hover:bg-fondo">Cancelar</a>
        <button type="submit" disabled={!valido || enviando}
          className="rounded bg-accion px-4 py-2 font-semibold text-white hover:bg-accion-hover disabled:cursor-not-allowed disabled:opacity-40">
          {enviando ? "Registrando…" : "Registrar y validar"}
        </button>
      </div>
    </form>
  );
}
