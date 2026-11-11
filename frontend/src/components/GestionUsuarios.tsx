// P16. Gestionar usuarios (CU-15, RF-15; Figura 17 y Tabla 17 de la Práctica 7). Solo el
// Administrador del sistema. La contraseña temporal se muestra una sola vez; la baja es lógica,
// irreversible y se confirma antes (H3). El Administrador no puede modificar su propia cuenta.
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ErrorApi, usuarios as servicio, type ContrasenaTemporal, type Rol, type Unidad, type Usuario, type UsuarioEntrada } from "../lib/api";
import { sesionActual } from "../lib/sesion";

const campo = "w-full rounded border border-linea bg-white px-3 py-2";
const etiqueta = "mb-1 block text-sm font-semibold";
const principal = "rounded bg-accion px-4 py-2 font-semibold text-white hover:bg-accion-hover disabled:cursor-not-allowed disabled:opacity-40";
const secundario = "rounded border border-linea bg-white px-4 py-2 font-semibold hover:bg-fondo disabled:opacity-40";
const enlace = "rounded px-2 py-1 text-sm font-semibold text-accion hover:bg-fondo";

type Formulario = { id: number | null } & UsuarioEntrada;
const VACIO: Formulario = { id: null, nombre_usuario: "", nombres_apellidos: "", codigo_rol: "AU", unidad_sigla: "" };

function Dialogo({ titulo, children, acciones }: { titulo: string; children: ReactNode; acciones: ReactNode }) {
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-tinta/50 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="titulo-dialogo" className="w-full max-w-md rounded bg-superficie p-5 shadow-lg">
        <h2 id="titulo-dialogo" className="text-lg font-bold">{titulo}</h2>
        <div className="mt-3 space-y-3 text-sm">{children}</div>
        <div className="mt-5 flex justify-end gap-3">{acciones}</div>
      </div>
    </div>
  );
}

function estadoCuenta(u: Usuario): { texto: string; clase: string } {
  if (u.estado === "BAJA") return { texto: "Baja", clase: "border-pizarra text-pizarra" };
  if (u.bloqueado) return { texto: "Bloqueado", clase: "border-rojo text-rojo bg-rojo-suave" };
  if (u.contrasena_temporal) return { texto: "Contraseña temporal", clase: "border-pizarra text-tinta bg-fondo" };
  return { texto: "Activo", clase: "border-verde text-verde bg-verde-suave" };
}

export default function GestionUsuarios() {
  const [roles, setRoles] = useState<Rol[]>([]);
  const [unidades, setUnidades] = useState<Unidad[]>([]);
  const [lista, setLista] = useState<Usuario[] | null>(null);
  const [miId, setMiId] = useState<number | null>(null);
  const [filtros, setFiltros] = useState({ rol: "", unidad: "", estado: "ACTIVO", buscar: "" });
  const [formulario, setFormulario] = useState<Formulario | null>(null);
  const [errorFormulario, setErrorFormulario] = useState("");
  const [temporal, setTemporal] = useState<ContrasenaTemporal | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [confirmar, setConfirmar] = useState<{ tipo: "baja" | "restablecer"; usuario: Usuario } | null>(null);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    sesionActual().then((u) => setMiId(u.id_usuario)).catch(() => undefined);
    servicio.catalogos().then((c) => { setRoles(c.roles); setUnidades(c.unidades); })
      .catch((e: ErrorApi) => setMensaje({ tipo: "error", texto: e.message }));
  }, []);

  const cargar = useCallback(() => {
    servicio.listar(filtros).then(setLista).catch((e: ErrorApi) => setMensaje({ tipo: "error", texto: e.message }));
  }, [filtros]);
  useEffect(() => {
    const espera = setTimeout(cargar, 250);  // el buscador filtra mientras se escribe (H7)
    return () => clearTimeout(espera);
  }, [cargar]);

  const nombreRol = (codigo: string) => roles.find((r) => r.codigo === codigo)?.nombre ?? codigo;
  const requiereUnidad = formulario?.codigo_rol === "AU";
  const conUnidad = formulario?.codigo_rol !== "ADM";
  const nombreValido = !formulario || formulario.id !== null || /^[a-z0-9._-]{3,30}$/.test(formulario.nombre_usuario.trim().toLowerCase());
  const formularioValido = formulario !== null && nombreValido && formulario.nombres_apellidos.trim() !== ""
    && (!requiereUnidad || !!formulario.unidad_sigla);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!formulario) return;
    setOcupado(true); setErrorFormulario("");
    const datos = {
      nombres_apellidos: formulario.nombres_apellidos.trim(), codigo_rol: formulario.codigo_rol,
      unidad_sigla: conUnidad && formulario.unidad_sigla ? formulario.unidad_sigla : null,
    };
    try {
      if (formulario.id === null) {
        const creado = await servicio.crear({ ...datos, nombre_usuario: formulario.nombre_usuario.trim().toLowerCase() });
        setTemporal(creado); setCopiado(false);
      } else {
        await servicio.modificar(formulario.id, datos);
        setMensaje({ tipo: "ok", texto: "Usuario actualizado. Si cambió su rol o su unidad, sus sesiones abiertas se cerraron." });
      }
      setFormulario(null);
      cargar();
    } catch (error) {
      const err = error as ErrorApi;
      setErrorFormulario(err.errores.length ? `${err.message} ${err.errores.map((x) => x.mensaje).join("; ")}` : err.message);
    } finally {
      setOcupado(false);
    }
  }

  async function ejecutarConfirmado() {
    if (!confirmar) return;
    setOcupado(true); setMensaje(null);
    try {
      if (confirmar.tipo === "baja") {
        await servicio.darDeBaja(confirmar.usuario.id_usuario);
        setMensaje({ tipo: "ok", texto: `Se dio de baja a ${confirmar.usuario.nombre_usuario}. Sus sesiones se cerraron y sus datos personales se reemplazaron por un seudónimo.` });
      } else {
        setTemporal(await servicio.restablecer(confirmar.usuario.id_usuario)); setCopiado(false);
      }
      cargar();
    } catch (error) {
      setMensaje({ tipo: "error", texto: (error as ErrorApi).message });
    } finally {
      setConfirmar(null); setOcupado(false);
    }
  }

  async function copiar() {
    if (!temporal) return;
    try { await navigator.clipboard.writeText(temporal.contrasena_temporal); setCopiado(true); } catch { setCopiado(false); }
  }

  return (
    <div className="space-y-4">
      {mensaje && (
        <p role={mensaje.tipo === "error" ? "alert" : "status"}
          className={`rounded border-l-4 p-3 text-sm ${mensaje.tipo === "error" ? "border-rojo bg-rojo-suave" : "border-verde bg-verde-suave"}`}>{mensaje.texto}</p>
      )}

      <div className="flex flex-wrap items-end gap-3 rounded border border-linea bg-superficie p-3">
        <div>
          <label htmlFor="f-rol" className={etiqueta}>Rol</label>
          <select id="f-rol" className={campo} value={filtros.rol} onChange={(e) => setFiltros({ ...filtros, rol: e.target.value })}>
            <option value="">Todos</option>
            {roles.map((r) => <option key={r.codigo} value={r.codigo}>{r.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-unidad" className={etiqueta}>Unidad orgánica</label>
          <select id="f-unidad" className={campo} value={filtros.unidad} onChange={(e) => setFiltros({ ...filtros, unidad: e.target.value })}>
            <option value="">Todas</option>
            {unidades.map((u) => <option key={u.sigla} value={u.sigla ?? ""}>{u.sigla} · {u.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-estado" className={etiqueta}>Estado</label>
          <select id="f-estado" className={campo} value={filtros.estado} onChange={(e) => setFiltros({ ...filtros, estado: e.target.value })}>
            <option value="">Todos</option>
            <option value="ACTIVO">Activo</option>
            <option value="BAJA">Baja</option>
          </select>
        </div>
        <div className="min-w-48 flex-1">
          <label htmlFor="f-buscar" className={etiqueta}>Buscar</label>
          <input id="f-buscar" type="search" className={campo} maxLength={60} placeholder="Usuario o nombre"
            value={filtros.buscar} onChange={(e) => setFiltros({ ...filtros, buscar: e.target.value })} />
        </div>
        <button type="button" className={principal}
          onClick={() => { setFormulario({ ...VACIO }); setErrorFormulario(""); }}>Nuevo usuario</button>
      </div>

      {lista === null ? <p className="text-pizarra">Cargando usuarios…</p> : lista.length === 0 ? (
        <p className="rounded border border-linea bg-superficie p-4 text-pizarra">No hay usuarios con esos filtros.</p>
      ) : (
        <div className="overflow-x-auto rounded border border-linea bg-superficie">
          <table className="w-full text-left text-sm">
            <thead className="bg-fondo text-pizarra">
              <tr>
                <th scope="col" className="px-3 py-2">Usuario</th>
                <th scope="col" className="px-3 py-2">Nombres y apellidos</th>
                <th scope="col" className="px-3 py-2">Rol</th>
                <th scope="col" className="px-3 py-2">Unidad</th>
                <th scope="col" className="px-3 py-2">Estado</th>
                <th scope="col" className="px-3 py-2"><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {lista.map((u) => {
                const estado = estadoCuenta(u);
                const propia = u.id_usuario === miId;
                return (
                  <tr key={u.id_usuario} className="border-t border-linea">
                    <td className="px-3 py-2 font-semibold">{u.nombre_usuario}</td>
                    <td className="px-3 py-2">{u.nombres_apellidos}</td>
                    <td className="px-3 py-2">{u.rol.nombre}</td>
                    <td className="px-3 py-2">{u.unidad?.sigla ?? "—"}</td>
                    <td className="px-3 py-2"><span className={`rounded border px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${estado.clase}`}>{estado.texto}</span></td>
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      {u.estado === "BAJA" ? null : propia ? <span className="text-xs text-pizarra">Su cuenta</span> : (
                        <>
                          <button type="button" className={enlace} onClick={() => {
                            setFormulario({ id: u.id_usuario, nombre_usuario: u.nombre_usuario, nombres_apellidos: u.nombres_apellidos,
                              codigo_rol: u.rol.codigo, unidad_sigla: u.unidad?.sigla ?? "" });
                            setErrorFormulario("");
                          }}>Editar</button>
                          <button type="button" className={enlace} onClick={() => setConfirmar({ tipo: "restablecer", usuario: u })}>Restablecer contraseña</button>
                          <button type="button" className={`${enlace} text-rojo`} onClick={() => setConfirmar({ tipo: "baja", usuario: u })}>Dar de baja</button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {formulario && (
        <Dialogo titulo={formulario.id === null ? "Nuevo usuario" : `Editar usuario ${formulario.nombre_usuario}`}
          acciones={<>
            <button type="button" className={secundario} onClick={() => setFormulario(null)}>Cancelar</button>
            <button type="submit" form="form-usuario" className={principal} disabled={!formularioValido || ocupado}>
              {ocupado ? "Guardando…" : "Guardar usuario"}</button>
          </>}>
          <form id="form-usuario" onSubmit={guardar} className="space-y-3" noValidate>
            {errorFormulario && <p role="alert" className="rounded border-l-4 border-rojo bg-rojo-suave p-2">{errorFormulario}</p>}
            {formulario.id === null && (
              <div>
                <label htmlFor="u-nombre" className={etiqueta}>Nombre de usuario <span aria-hidden="true">*</span></label>
                <input id="u-nombre" className={campo} maxLength={30} autoComplete="off" spellCheck={false} required
                  value={formulario.nombre_usuario} onChange={(e) => setFormulario({ ...formulario, nombre_usuario: e.target.value })}
                  aria-describedby="u-nombre-ayuda" aria-invalid={!nombreValido} />
                <p id="u-nombre-ayuda" className={`mt-1 text-xs ${nombreValido ? "text-pizarra" : "text-rojo"}`}>
                  De 3 a 30 caracteres: letras minúsculas, números, punto, guion o guion bajo. No use el DNI.</p>
              </div>
            )}
            <div>
              <label htmlFor="u-nombres" className={etiqueta}>Nombres y apellidos <span aria-hidden="true">*</span></label>
              <input id="u-nombres" className={campo} maxLength={120} required value={formulario.nombres_apellidos}
                onChange={(e) => setFormulario({ ...formulario, nombres_apellidos: e.target.value })} />
            </div>
            <div>
              <label htmlFor="u-rol" className={etiqueta}>Rol <span aria-hidden="true">*</span></label>
              <select id="u-rol" className={campo} value={formulario.codigo_rol}
                onChange={(e) => setFormulario({ ...formulario, codigo_rol: e.target.value as Rol["codigo"] })}>
                {roles.map((r) => <option key={r.codigo} value={r.codigo}>{nombreRol(r.codigo)}</option>)}
              </select>
            </div>
            {conUnidad && (
              <div>
                <label htmlFor="u-unidad" className={etiqueta}>Unidad orgánica {requiereUnidad && <span aria-hidden="true">*</span>}</label>
                <select id="u-unidad" className={campo} value={formulario.unidad_sigla ?? ""}
                  onChange={(e) => setFormulario({ ...formulario, unidad_sigla: e.target.value })}>
                  <option value="">{requiereUnidad ? "Seleccione…" : "Sin unidad"}</option>
                  {unidades.map((u) => <option key={u.sigla} value={u.sigla ?? ""}>{u.sigla} · {u.nombre}</option>)}
                </select>
                {requiereUnidad && <p className="mt-1 text-xs text-pizarra">Obligatoria para el Área Usuaria: solo verá los requerimientos de esta unidad.</p>}
              </div>
            )}
            {formulario.id !== null && <p className="text-xs text-pizarra">Si cambia el rol o la unidad, se cerrarán las sesiones abiertas del usuario.</p>}
            <p className="text-xs text-pizarra">* Campos obligatorios.</p>
          </form>
        </Dialogo>
      )}

      {confirmar && (
        <Dialogo titulo={confirmar.tipo === "baja" ? "¿Dar de baja al usuario?" : "¿Restablecer la contraseña?"}
          acciones={<>
            <button type="button" className={secundario} onClick={() => setConfirmar(null)} disabled={ocupado}>Cancelar</button>
            <button type="button" onClick={ejecutarConfirmado} disabled={ocupado}
              className={confirmar.tipo === "baja" ? "rounded bg-rojo px-4 py-2 font-semibold text-white disabled:opacity-40" : principal}>
              {confirmar.tipo === "baja" ? "Dar de baja" : "Restablecer"}</button>
          </>}>
          {confirmar.tipo === "baja" ? (
            <p>Se dará de baja a <strong>{confirmar.usuario.nombre_usuario}</strong> ({confirmar.usuario.nombres_apellidos}). Se cerrarán sus sesiones y sus datos personales se reemplazarán por un seudónimo. <strong>Esta acción no se puede deshacer.</strong></p>
          ) : (
            <p>Se generará una contraseña temporal para <strong>{confirmar.usuario.nombre_usuario}</strong>, se desbloqueará la cuenta y se cerrarán sus sesiones. La contraseña actual dejará de funcionar.</p>
          )}
        </Dialogo>
      )}

      {temporal && (
        <Dialogo titulo="Contraseña temporal"
          acciones={<button type="button" className={principal} onClick={() => setTemporal(null)}>Ya la entregué, cerrar</button>}>
          <p>Entregue esta contraseña a <strong>{temporal.usuario.nombres_apellidos}</strong> (usuario <strong>{temporal.usuario.nombre_usuario}</strong>) de forma personal. Deberá cambiarla en su primer ingreso.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded border border-linea bg-fondo px-3 py-2 text-base tracking-wider">{temporal.contrasena_temporal}</code>
            <button type="button" className={secundario} onClick={copiar}>{copiado ? "Copiada" : "Copiar"}</button>
          </div>
          <p role="status" className="rounded border-l-4 border-ambar bg-ambar-suave p-2">Se muestra una sola vez: el sistema no la guarda y no podrá volver a verla.</p>
        </Dialogo>
      )}
    </div>
  );
}
