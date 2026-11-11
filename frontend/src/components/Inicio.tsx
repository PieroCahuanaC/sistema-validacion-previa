// P02. Inicio (menú según rol; Figura 2 y Tabla 3 de la Práctica 7). Muestra la fecha de corte
// de los datos y, para el Área Usuaria, el resumen por semáforo y «Pendientes de su acción».
import { useEffect, useState } from "react";
import type { ErrorApi, Inicio as DatosInicio, UsuarioSesion } from "../lib/api";
import { formatoFecha, formatoFechaHora } from "../lib/formato";
import { inicioActual, sesionActual } from "../lib/sesion";

const SITUACION: Record<string, string> = {
  Verde: "bg-verde-suave text-verde border-verde",
  "Ámbar": "bg-ambar-suave text-ambar border-ambar",
  Rojo: "bg-rojo-suave text-rojo border-rojo",
  Observado: "bg-fondo text-tinta border-pizarra",
};

function Tarjeta({ titulo, valor, color }: { titulo: string; valor: number; color?: string }) {
  return (
    <div className={`rounded border border-linea bg-superficie p-4 ${color ? `border-l-8 ${color}` : ""}`}
      title="Mis requerimientos (P17) se habilita en el siguiente incremento">
      <p className="text-sm text-pizarra">{titulo}</p>
      <p className="cifra mt-1 text-3xl font-bold">{valor}</p>
    </div>
  );
}

export default function Inicio() {
  const [usuario, setUsuario] = useState<UsuarioSesion | null>(null);
  const [datos, setDatos] = useState<DatosInicio | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    sesionActual().then(setUsuario).catch(() => undefined);
    inicioActual().then(setDatos).catch((e: ErrorApi) => setError(e.message));
  }, []);

  if (error) return <p role="alert" className="rounded border border-rojo bg-rojo-suave p-3">{error}</p>;
  if (!usuario || !datos) return <p className="text-pizarra">Cargando…</p>;

  const rol = usuario.rol.codigo;
  return (
    <div className="space-y-6">
      <p className="text-lg">Bienvenido(a), <strong>{usuario.nombres_apellidos}</strong>.</p>

      <div role="status" className="rounded border-l-4 border-accion bg-superficie p-3 text-sm">
        Datos presupuestales al <strong>{formatoFecha(datos.fecha_corte_mef)}</strong> (Consulta Amigable del MEF)
        {" · "}Plan Anual de Contrataciones al <strong>{formatoFecha(datos.fecha_corte_seace)}</strong> (SEACE).
      </div>

      {rol === "ADM" && (
        <section className="rounded border border-linea bg-superficie p-5">
          <h2 className="text-lg font-semibold">Administración del sistema</h2>
          <p className="mt-1 text-pizarra">Cree las cuentas, asigne roles y unidades orgánicas, restablezca contraseñas y dé de baja usuarios.</p>
          <a href="/usuarios" className="mt-4 inline-block rounded bg-accion px-4 py-2 font-semibold text-white hover:bg-accion-hover">Gestionar usuarios</a>
        </section>
      )}

      {datos.tarjetas && (
        <section aria-labelledby="titulo-resumen">
          <h2 id="titulo-resumen" className="mb-3 text-lg font-semibold">Requerimientos de su unidad{usuario.unidad?.sigla ? ` (${usuario.unidad.sigla})` : ""}</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Tarjeta titulo="Verde" valor={datos.tarjetas.verde} color="border-l-verde" />
            <Tarjeta titulo="Ámbar" valor={datos.tarjetas.ambar} color="border-l-ambar" />
            <Tarjeta titulo="Rojo" valor={datos.tarjetas.rojo} color="border-l-rojo" />
            <Tarjeta titulo="Observado" valor={datos.tarjetas.observado} />
            <Tarjeta titulo="Con cuello de botella" valor={datos.tarjetas.cuello_de_botella} />
          </div>
        </section>
      )}

      {rol !== "ADM" && (
        <section id="pendientes" aria-labelledby="titulo-pendientes" className="scroll-mt-20">
          <h2 id="titulo-pendientes" className="mb-3 text-lg font-semibold">Pendientes de su acción</h2>
          {!datos.pendientes_disponibles ? (
            <p className="rounded border border-linea bg-superficie p-4 text-pizarra">
              Su lista de pendientes se habilita junto con las pantallas de su rol en el siguiente incremento.
            </p>
          ) : datos.pendientes.length === 0 ? (
            <p className="rounded border border-linea bg-superficie p-4 text-pizarra">No tiene requerimientos que esperen su acción.</p>
          ) : (
            <div className="overflow-x-auto rounded border border-linea bg-superficie">
              <table className="w-full text-left text-sm">
                <thead className="bg-fondo text-pizarra">
                  <tr>
                    <th scope="col" className="px-3 py-2">Código</th>
                    <th scope="col" className="px-3 py-2">Descripción</th>
                    <th scope="col" className="px-3 py-2">Situación</th>
                    <th scope="col" className="px-3 py-2">Motivo</th>
                    <th scope="col" className="px-3 py-2">Desde</th>
                    <th scope="col" className="px-3 py-2"><span className="sr-only">Acción</span></th>
                  </tr>
                </thead>
                <tbody>
                  {datos.pendientes.map((p) => (
                    <tr key={p.requerimiento_id} className="border-t border-linea">
                      <td className="px-3 py-2 font-semibold whitespace-nowrap">{p.codigo}</td>
                      <td className="max-w-xs px-3 py-2">{p.descripcion}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded border px-2 py-0.5 text-xs font-semibold ${SITUACION[p.situacion] ?? ""}`}>{p.situacion}</span>
                      </td>
                      <td className="px-3 py-2">{p.motivo}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{formatoFechaHora(p.desde)}</td>
                      <td className="px-3 py-2 text-right">
                        <a href={p.destino} className="inline-block rounded bg-accion px-3 py-1.5 font-semibold whitespace-nowrap text-white hover:bg-accion-hover">{p.accion}</a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
