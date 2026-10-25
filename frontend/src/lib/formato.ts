// Formatos de la municipalidad: montos en S/ y fechas dd/mm/aaaa (heurística H2 de Nielsen).
const soles = new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" });

export const formatoSoles = (valor: string | number | null | undefined): string =>
  valor === null || valor === undefined || valor === "" ? "—" : soles.format(Number(valor));

export const formatoFecha = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
};

export const formatoFechaHora = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-PE", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    timeZone: "America/Lima",
  });
};

export const hoyLima = (): string =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "America/Lima" }).format(new Date());
