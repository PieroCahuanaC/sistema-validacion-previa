// P14. Configurar reglas del semáforo (CU-12, RF-03, RNF-04; Figura 15 y Tabla 15 de la
// Práctica 7). Cada cambio crea una versión nueva; las validaciones ya registradas conservan
// la versión con que se calcularon.
import { useEffect, useState } from "react";
import { api, ErrorApi, type ParametrosSemaforo, type Reglas } from "../lib/api";
import { formatoFechaHora, formatoSoles } from "../lib/formato";
import { Aviso, campo, Confirmacion, etiqueta, principal, secundario } from "./comunes";

type Formulario = { umbral: string; columna: ParametrosSemaforo["columna_comparacion"]; pac: ParametrosSemaforo["tratamiento_no_previsto_pac"]; antiguedad: string; uit: string };

const desdeParametros = (p: ParametrosSemaforo): Formulario => ({
  umbral: String(p.umbral_disponibilidad_pct), columna: p.columna_comparacion,
  pac: p.tratamiento_no_previsto_pac, antiguedad: String(p.antiguedad_maxima_dias), uit: Number(p.valor_uit).toFixed(2),
});

const VALOR_LEGIBLE: Record<string, (v: string) => string> = {
  umbral_disponibilidad_pct: (v) => `${v} %`,
  columna_comparacion: (v) => (v === "COMPROMISO" ? "Compromiso anual" : "Certificación"),
  tratamiento_no_previsto_pac: (v) => (v === "AMBAR" ? "Ámbar" : "Verde"),
  antiguedad_maxima_dias: (v) => `${v} días`,
  valor_uit: (v) => formatoSoles(v),
};

function errores(f: Formulario): Partial<Record<keyof Formulario, string>> {
  const e: Partial<Record<keyof Formulario, string>> = {};
  const umbral = Number(f.umbral), dias = Number(f.antiguedad), uit = Number(f.uit);
  if (!/^\d+$/.test(f.umbral) || umbral < 100 || umbral > 200) e.umbral = "Ingrese un número entero de 100 a 200.";
  if (!/^\d+$/.test(f.antiguedad) || dias < 1 || dias > 31) e.antiguedad = "Ingrese un número entero de 1 a 31.";
  if (!/^\d+(\.\d{1,2})?$/.test(f.uit) || uit <= 0 || uit > 99999.99) e.uit = "Ingrese un monto mayor que 0, con hasta dos decimales.";
  return e;
}

function Modificado({ visible }: { visible: boolean }) {
  return visible ? <span className="ml-2 rounded bg-ambar-suave px-1.5 py-0.5 text-xs font-semibold text-ambar">Modificado</span> : null;
}

export default function ConfigurarReglas() {
  const [reglas, setReglas] = useState<Reglas | null>(null);
  const [form, setForm] = useState<Formulario | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  const cargar = (mensaje?: string) => api.reglas().then((r) => {
    setReglas(r); setForm(desdeParametros(r.parametros));
    if (mensaje) setAviso({ tipo: "ok", texto: mensaje });
  }).catch((e: ErrorApi) => setAviso({ tipo: "error", texto: e.message }));
  useEffect(() => { cargar(); }, []);

  const vigente = reglas ? desdeParametros(reglas.parametros) : null;
  const fallas = form ? errores(form) : {};
  const cambiados = form && vigente
    ? (Object.keys(form) as (keyof Formulario)[]).filter((k) => form[k] !== vigente[k]) : [];
  const valido = Object.keys(fallas).length === 0;

  if (!reglas || !form || !vigente) return aviso ? <Aviso tipo="error">{aviso.texto}</Aviso> : <p className="text-pizarra">Cargando…</p>;

  const parametros: ParametrosSemaforo = {
    umbral_disponibilidad_pct: Number(form.umbral), columna_comparacion: form.columna,
    tratamiento_no_previsto_pac: form.pac, antiguedad_maxima_dias: Number(form.antiguedad), valor_uit: Number(form.uit).toFixed(2),
  };
  const guardar = async () => {
    setOcupado(true);
    try {
      await api.guardarRegla(parametros);
      setConfirmar(false);
      await cargar("Se registró la nueva versión de la regla. Rige para las validaciones desde ahora.");
    } catch (e) {
      setConfirmar(false);
      setAviso({ tipo: "error", texto: (e as ErrorApi).message });
    } finally { setOcupado(false); }
  };
  const nombres: Record<keyof Formulario, string> = {
    umbral: "Umbral de disponibilidad", columna: "Columna que se resta del PIM", pac: "Tratamiento de lo no previsto en el PAC",
    antiguedad: "Antigüedad máxima del dato", uit: "Valor de la UIT",
  };
  const opcion = "flex items-start gap-2 rounded border border-linea p-2 text-sm";

  return (
    <div className="space-y-6">
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
      <p className="text-sm text-pizarra">La versión vigente (N.° {reglas.id_regla}, desde el <strong className="text-tinta">{formatoFechaHora(reglas.vigente_desde)}</strong>) se aplica a cada validación nueva.
        Los requerimientos ya validados conservan la versión con que se calcularon.</p>

      <form className="space-y-5 rounded border border-linea bg-superficie p-5" onSubmit={(e) => { e.preventDefault(); if (valido && cambiados.length) setConfirmar(true); }}>
        <div className="grid gap-5 lg:grid-cols-2">
          <div>
            <label htmlFor="r-umbral" className={etiqueta}>Umbral de disponibilidad (%) *<Modificado visible={cambiados.includes("umbral")} /></label>
            <input id="r-umbral" inputMode="numeric" className={campo} value={form.umbral} aria-invalid={!!fallas.umbral}
              aria-describedby="r-umbral-ayuda" onChange={(e) => setForm({ ...form, umbral: e.target.value.trim() })} />
            <p id="r-umbral-ayuda" className={`mt-1 text-xs ${fallas.umbral ? "text-rojo" : "text-pizarra"}`}>
              {fallas.umbral ? `${fallas.umbral} Se conserva el valor vigente hasta que lo corrija.`
                : "Verde exige que el saldo presupuestal disponible cubra el monto por este porcentaje: 100 % es que alcance justo; 120 % deja un margen de 20 %. Rango: 100 a 200."}
            </p>
          </div>
          <div>
            <label htmlFor="r-antiguedad" className={etiqueta}>Antigüedad máxima del dato (días) *<Modificado visible={cambiados.includes("antiguedad")} /></label>
            <input id="r-antiguedad" inputMode="numeric" className={campo} value={form.antiguedad} aria-invalid={!!fallas.antiguedad}
              aria-describedby="r-antiguedad-ayuda" onChange={(e) => setForm({ ...form, antiguedad: e.target.value.trim() })} />
            <p id="r-antiguedad-ayuda" className={`mt-1 text-xs ${fallas.antiguedad ? "text-rojo" : "text-pizarra"}`}>
              {fallas.antiguedad ? `${fallas.antiguedad} Se conserva el valor vigente hasta que lo corrija.`
                : "Si la fecha de corte de los datos del MEF es más antigua, el semáforo sale ámbar (dato desactualizado). Rango: 1 a 31."}
            </p>
          </div>
          <fieldset>
            <legend className={etiqueta}>Columna que se resta del PIM *<Modificado visible={cambiados.includes("columna")} /></legend>
            <div className="space-y-2">
              <label className={opcion}><input type="radio" name="columna" checked={form.columna === "COMPROMISO"} onChange={() => setForm({ ...form, columna: "COMPROMISO" })} />
                <span><strong>Compromiso anual.</strong> Saldo = PIM − compromiso anual: lo aún no comprometido.</span></label>
              <label className={opcion}><input type="radio" name="columna" checked={form.columna === "CERTIFICACION"} onChange={() => setForm({ ...form, columna: "CERTIFICACION" })} />
                <span><strong>Certificación.</strong> Saldo = PIM − certificación: más conservador, descuenta también lo ya certificado.</span></label>
            </div>
          </fieldset>
          <fieldset>
            <legend className={etiqueta}>Tratamiento de lo no previsto en el PAC *<Modificado visible={cambiados.includes("pac")} /></legend>
            <div className="space-y-2">
              <label className={opcion}><input type="radio" name="pac" checked={form.pac === "AMBAR"} onChange={() => setForm({ ...form, pac: "AMBAR" })} />
                <span><strong>Ámbar.</strong> Presupuesto decide en el panel de alertas si confirma la disponibilidad.</span></label>
              <label className={opcion}><input type="radio" name="pac" checked={form.pac === "VERDE"} onChange={() => setForm({ ...form, pac: "VERDE" })} />
                <span><strong>Verde.</strong> Si hay saldo, continúa sin pasar por Presupuesto.</span></label>
            </div>
          </fieldset>
          <div>
            <label htmlFor="r-uit" className={etiqueta}>Valor de la UIT (S/) *<Modificado visible={cambiados.includes("uit")} /></label>
            <input id="r-uit" inputMode="decimal" className={`${campo} cifra`} value={form.uit} aria-invalid={!!fallas.uit}
              aria-describedby="r-uit-ayuda" onChange={(e) => setForm({ ...form, uit: e.target.value.trim().replace(",", ".") })} />
            <p id="r-uit-ayuda" className={`mt-1 text-xs ${fallas.uit ? "text-rojo" : "text-pizarra"}`}>
              {fallas.uit ? `${fallas.uit} Se conserva el valor vigente hasta que lo corrija.`
                : <>Fija el tope de 8 UIT del registro: <strong>{formatoSoles(Number(form.uit) * 8)}</strong>. Actualícelo cuando el MEF apruebe la UIT del nuevo año.</>}
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t border-linea pt-4">
          <button type="button" className={secundario} disabled={!cambiados.length} onClick={() => { setForm(vigente); setAviso(null); }}>Cancelar</button>
          <button type="submit" className={principal} disabled={!valido || !cambiados.length}>Guardar nueva versión</button>
        </div>
      </form>

      <section aria-labelledby="titulo-versiones">
        <h2 id="titulo-versiones" className="mb-3 text-lg font-semibold">Historial de versiones</h2>
        <div className="overflow-x-auto rounded border border-linea bg-superficie">
          <table className="w-full text-left text-sm">
            <thead className="bg-fondo text-pizarra">
              <tr><th scope="col" className="px-3 py-2">Versión</th><th scope="col" className="px-3 py-2">Vigente desde</th>
                <th scope="col" className="px-3 py-2">Vigente hasta</th><th scope="col" className="px-3 py-2">Cambios (anterior → nuevo)</th>
                <th scope="col" className="px-3 py-2">Registrado por</th></tr>
            </thead>
            <tbody>
              {reglas.historial.map((v) => (
                <tr key={v.id_regla} className="border-t border-linea align-top">
                  <td className="px-3 py-2 font-semibold">N.° {v.id_regla}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{formatoFechaHora(v.vigente_desde)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{v.vigente_hasta ? formatoFechaHora(v.vigente_hasta) : <strong className="text-verde">Vigente</strong>}</td>
                  <td className="px-3 py-2">
                    {v.cambios.length === 0 ? <span className="text-pizarra">Versión inicial</span> : (
                      <ul className="space-y-0.5">{v.cambios.map((c) => (
                        <li key={c.parametro}>{c.etiqueta}: {VALOR_LEGIBLE[c.parametro]?.(c.anterior) ?? c.anterior} → <strong>{VALOR_LEGIBLE[c.parametro]?.(c.nuevo) ?? c.nuevo}</strong></li>
                      ))}</ul>
                    )}
                  </td>
                  <td className="px-3 py-2">{v.registrado_por}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {confirmar && (
        <Confirmacion titulo="¿Guardar una nueva versión de la regla?" textoAccion="Guardar nueva versión" ocupado={ocupado}
          onConfirmar={guardar} onCancelar={() => setConfirmar(false)}>
          <p>Se cerrará la versión vigente y la nueva regirá para las validaciones desde ahora:</p>
          <ul className="list-disc pl-5">{cambiados.map((k) => <li key={k}>{nombres[k]}</li>)}</ul>
          <p>Los requerimientos ya validados no cambian. El cambio queda registrado en la bitácora.</p>
        </Confirmacion>
      )}
    </div>
  );
}
