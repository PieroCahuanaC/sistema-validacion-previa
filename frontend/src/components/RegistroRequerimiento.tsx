// P03. Registrar requerimiento: una sola pantalla en dos pasos (cambio 15 de la Práctica 7).
// Sin parámetro se muestra el paso 1; con ?id= (desde «Completar paso 2» de la P04), el paso 2.
import FormularioRequerimiento from "./FormularioRequerimiento";
import Paso2Requerimiento from "./Paso2Requerimiento";

export default function RegistroRequerimiento() {
  const id = typeof window !== "undefined" ? Number(new URLSearchParams(window.location.search).get("id")) : 0;
  return id > 0 ? <Paso2Requerimiento id={id} /> : <FormularioRequerimiento />;
}
