// Indicador de los pasos del registro (P03 en dos pasos, cambio 15 de la Práctica 7):
// primero se valida el presupuesto; las especificaciones y los documentos van después.
const PASOS = [
  { n: 1, texto: "Datos presupuestales y validación", nota: "" },
  { n: 2, texto: "Especificaciones y documentos", nota: "solo con semáforo verde" },
  { n: 3, texto: "Envío a la Gerencia de Administración", nota: "" },
];

export default function PasosRegistro({ actual }: { actual: 1 | 2 | 3 }) {
  return (
    <ol aria-label="Pasos del registro" className="mb-4 grid gap-2 rounded border border-linea bg-superficie p-3 md:grid-cols-3">
      {PASOS.map((p) => {
        const hecho = p.n < actual;
        const activo = p.n === actual;
        return (
          <li key={p.n} aria-current={activo ? "step" : undefined}
            className={`flex items-center gap-2 text-sm ${activo ? "font-semibold" : hecho ? "" : "text-pizarra"}`}>
            <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs ${
              activo ? "border-accion bg-accion text-white" : hecho ? "border-accion text-accion" : "border-linea"}`}>
              {hecho ? "✓" : p.n}
            </span>
            <span>{p.texto}{p.nota && <span className="ml-1 text-xs font-normal text-pizarra">({p.nota})</span>}</span>
          </li>
        );
      })}
    </ol>
  );
}
