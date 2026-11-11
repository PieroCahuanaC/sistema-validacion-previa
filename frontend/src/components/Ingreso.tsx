// P01. Iniciar sesión (CU-09, RF-10; Figura 1 y Tabla 2 de la Práctica 7). Estados: ingreso,
// intentos restantes, cuenta bloqueada hasta una hora, error del sistema con código de
// referencia y cambio obligatorio de la contraseña temporal.
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { auth, ErrorApi, type UsuarioSesion } from "../lib/api";
import { rutaInterna } from "../lib/sesion";

const campo = "w-full rounded border border-linea bg-white px-3 py-2";
const etiqueta = "mb-1 block text-sm font-semibold";
const principal = "rounded bg-accion px-4 py-2 font-semibold text-white hover:bg-accion-hover disabled:cursor-not-allowed disabled:opacity-40";
const secundario = "rounded border border-linea bg-white px-4 py-2 font-semibold hover:bg-fondo";
const LONGITUD_MINIMA = 12;

type Aviso = { tipo: "info" | "error" | "ok"; texto: string; referencia?: string };

function CampoClave({ id, etiquetaTexto, valor, onChange, autoComplete }: {
  id: string; etiquetaTexto: string; valor: string; onChange: (v: string) => void; autoComplete: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label htmlFor={id} className={etiqueta}>{etiquetaTexto} <span aria-hidden="true">*</span></label>
      <div className="flex gap-2">
        <input id={id} type={visible ? "text" : "password"} value={valor} required maxLength={128}
          autoComplete={autoComplete} onChange={(e) => onChange(e.target.value)} className={campo} />
        <button type="button" onClick={() => setVisible(!visible)} aria-pressed={visible}
          aria-controls={id} className={`${secundario} shrink-0 px-3 text-sm`}>{visible ? "Ocultar" : "Mostrar"}</button>
      </div>
    </div>
  );
}

function CuadroAviso({ aviso }: { aviso: Aviso }) {
  const estilo = { info: "border-accion bg-fondo", error: "border-rojo bg-rojo-suave", ok: "border-verde bg-verde-suave" }[aviso.tipo];
  return (
    <div role={aviso.tipo === "error" ? "alert" : "status"} className={`rounded border-l-4 p-3 text-sm ${estilo}`}>
      <p>{aviso.texto}</p>
      {aviso.referencia && <p className="mt-1 font-mono text-xs">Código de referencia: {aviso.referencia}</p>}
    </div>
  );
}

const horaLima = (iso: string) =>
  new Date(iso).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", timeZone: "America/Lima" });

export default function Ingreso() {
  const parametros = useMemo(() => new URLSearchParams(window.location.search), []);
  const destino = rutaInterna(parametros.get("volver"));
  const [nombre, setNombre] = useState("");
  const [clave, setClave] = useState("");
  const [aviso, setAviso] = useState<Aviso | null>(() => {
    if (parametros.get("salida")) return { tipo: "ok", texto: "Cerró sesión correctamente." };
    if (parametros.get("volver")) return { tipo: "info", texto: "Su sesión terminó. Inicie sesión para continuar." };
    return null;
  });
  const [bloqueadoHasta, setBloqueadoHasta] = useState<Date | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [temporal, setTemporal] = useState<UsuarioSesion | null>(null);
  const [verificando, setVerificando] = useState(true);

  // Si ya hay sesión, se continúa sin pedir de nuevo la contraseña.
  useEffect(() => {
    auth.yo().then((u) => {
      if (u && !u.contrasena_temporal) window.location.replace(destino);
      else { if (u) setTemporal(u); setVerificando(false); }
    }).catch(() => setVerificando(false));
  }, [destino]);

  // Ingresar queda deshabilitado hasta la hora indicada y se rehabilita solo.
  useEffect(() => {
    if (!bloqueadoHasta) return;
    const espera = bloqueadoHasta.getTime() - Date.now();
    const temporizador = setTimeout(() => { setBloqueadoHasta(null); setAviso(null); }, Math.max(0, espera) + 500);
    return () => clearTimeout(temporizador);
  }, [bloqueadoHasta]);

  async function ingresar(e: FormEvent) {
    e.preventDefault();
    setOcupado(true); setAviso(null);
    try {
      const usuario = await auth.ingresar(nombre.trim(), clave);
      if (usuario.contrasena_temporal) { setTemporal(usuario); setOcupado(false); return; }
      window.location.href = destino;
    } catch (error) {
      const err = error as ErrorApi;
      const restantes = err.datos.intentos_restantes as number | undefined;
      const hasta = err.datos.bloqueado_hasta as string | undefined;
      if (err.estado === 423 && hasta) {
        setBloqueadoHasta(new Date(hasta));
        setAviso({ tipo: "error", texto: `La cuenta está bloqueada temporalmente por tres intentos fallidos. Podrá intentarlo de nuevo desde las ${horaLima(hasta)} (hora de Lima); si no recuerda su contraseña, solicite al Administrador del sistema que la restablezca.` });
      } else if (err.estado === 401) {
        setAviso({ tipo: "error", texto: restantes === undefined ? err.message
          : `${err.message} Le ${restantes === 1 ? "queda 1 intento" : `quedan ${restantes} intentos`} antes de que la cuenta se bloquee por 15 minutos.` });
      } else {
        setAviso({ tipo: "error", texto: err.message, referencia: err.datos.codigo_referencia as string | undefined });
      }
      setClave("");
      setOcupado(false);
    }
  }

  if (verificando) return <p className="text-center text-pizarra">Verificando la sesión…</p>;
  if (temporal) {
    return <CambioTemporal usuario={temporal} claveActual={clave} destino={destino}
      onVolver={async () => {
        try { await auth.salir(); } catch { /* sin conexión: igual se vuelve al ingreso */ }
        setTemporal(null); setClave(""); setAviso(null);
      }} />;
  }

  return (
    <form onSubmit={ingresar} className="space-y-4" noValidate>
      <h2 className="text-xl font-bold">Iniciar sesión</h2>
      {aviso && <CuadroAviso aviso={aviso} />}
      <div>
        <label htmlFor="usuario" className={etiqueta}>Usuario <span aria-hidden="true">*</span></label>
        <input id="usuario" value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={30}
          autoComplete="username" autoCapitalize="none" spellCheck={false} required autoFocus className={campo} />
      </div>
      <CampoClave id="contrasena" etiquetaTexto="Contraseña" valor={clave} onChange={setClave} autoComplete="current-password" />
      <p className="text-xs text-pizarra">* Campos obligatorios. Las cuentas las crea el Administrador del sistema.</p>
      <div className="flex justify-end">
        <button type="submit" className={principal}
          disabled={ocupado || !nombre.trim() || !clave || bloqueadoHasta !== null}>
          {ocupado ? "Ingresando…" : "Ingresar"}</button>
      </div>
      {bloqueadoHasta && <p className="text-right text-xs text-pizarra">Ingresar se habilita a las {horaLima(bloqueadoHasta.toISOString())}.</p>}
    </form>
  );
}

function CambioTemporal({ usuario, claveActual, destino, onVolver }: {
  usuario: UsuarioSesion; claveActual: string; destino: string; onVolver: () => void;
}) {
  const [actual, setActual] = useState(claveActual);
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [aviso, setAviso] = useState<Aviso | null>(null);
  const [ocupado, setOcupado] = useState(false);

  // Reglas que pueden comprobarse mientras se escribe; la de contraseñas comunes la verifica
  // el servidor y, si falla, se marca con su mensaje.
  const [rechazadas, setRechazadas] = useState<string[]>([]);
  const cumple = [
    nueva.length >= LONGITUD_MINIMA,
    nueva.length > 0 && !rechazadas.includes(usuario.reglas_contrasena[1]),
    nueva.length > 0 && !nueva.toLowerCase().includes(usuario.nombre_usuario.toLowerCase()),
  ];
  const coincide = nueva.length > 0 && nueva === confirmacion;
  const listo = actual.length > 0 && cumple.every(Boolean) && coincide;

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setOcupado(true); setAviso(null);
    try {
      await auth.cambiarContrasena(actual, nueva);
      window.location.href = destino;
    } catch (error) {
      const err = error as ErrorApi;
      const reglas = (err.datos.reglas as string[] | undefined) ?? [];
      setRechazadas(reglas);
      setAviso({ tipo: "error", texto: reglas.length ? `${err.message} Revise: ${reglas.join("; ")}.` : err.message,
        referencia: err.datos.codigo_referencia as string | undefined });
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-4" noValidate>
      <h2 className="text-xl font-bold">Cambiar contraseña temporal</h2>
      <CuadroAviso aviso={{ tipo: "info", texto: "Ingresó con una contraseña temporal. Para continuar, defina una contraseña personal que solo usted conozca." }} />
      {aviso && <CuadroAviso aviso={aviso} />}
      <div>
        <span className={etiqueta}>Usuario</span>
        <p className="rounded border border-linea bg-fondo px-3 py-2">{usuario.nombre_usuario}</p>
      </div>
      {!claveActual && (
        <CampoClave id="actual" etiquetaTexto="Contraseña temporal" valor={actual} onChange={setActual} autoComplete="current-password" />
      )}
      <CampoClave id="nueva" etiquetaTexto="Nueva contraseña" valor={nueva}
        onChange={(v) => { setNueva(v); setRechazadas([]); }} autoComplete="new-password" />
      <ul className="space-y-1 text-sm" aria-label="Reglas de la contraseña">
        {usuario.reglas_contrasena.map((regla, i) => {
          const falla = rechazadas.includes(regla);
          const enServidor = i === 1 && !falla;
          const estado = falla ? "no cumple" : enServidor ? "se verifica al guardar" : cumple[i] ? "cumple" : "pendiente";
          return (
            <li key={regla} className={falla ? "text-rojo" : cumple[i] && !enServidor ? "text-verde" : "text-pizarra"}>
              <span aria-hidden="true">{falla ? "✖" : enServidor ? "•" : cumple[i] ? "✔" : "○"}</span> {regla}
              <span className={enServidor ? "text-xs" : "sr-only"}> ({estado})</span>
            </li>
          );
        })}
      </ul>
      <CampoClave id="confirmacion" etiquetaTexto="Confirmar contraseña" valor={confirmacion} onChange={setConfirmacion} autoComplete="new-password" />
      {confirmacion && !coincide && <p role="alert" className="text-sm text-rojo">La confirmación no coincide con la nueva contraseña.</p>}
      <div className="flex justify-end gap-3">
        <button type="button" onClick={onVolver} className={secundario}>Volver</button>
        <button type="submit" className={principal} disabled={!listo || ocupado}>
          {ocupado ? "Guardando…" : "Guardar y continuar"}</button>
      </div>
    </form>
  );
}
