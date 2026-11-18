// Verifica que la política de seguridad de contenidos de vercel.json (defecto DEF-04 de la
// Práctica 9) autorice cada script y estilo en línea del sitio compilado, y nada más.
//
// La política no usa 'unsafe-inline': autoriza los pocos bloques en línea que genera Astro (el
// arranque de las islas de React y el script del menú) por su resumen SHA-256. Si un cambio de
// Astro o del código cambia esos bloques, el sitio dejaría de funcionar en Vercel; por eso el
// pipeline ejecuta este script después de compilar y falla con los resúmenes que hay que copiar.
//
// Uso: node scripts/verificar-csp.mjs        (después de npm run build)
import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const DIST = "dist";
const politica = JSON.parse(readFileSync("vercel.json", "utf8"))
  .headers.flatMap((h) => h.headers)
  .find((h) => h.key.toLowerCase() === "content-security-policy").value;

const directiva = (nombre) => {
  const d = politica.split(";").map((x) => x.trim()).find((x) => x.startsWith(`${nombre} `));
  return new Set((d ?? "").split(/\s+/).slice(1));
};
const permitidos = { "script-src": directiva("script-src"), "style-src": directiva("style-src") };

const paginas = (carpeta) => readdirSync(carpeta, { withFileTypes: true }).flatMap((e) =>
  e.isDirectory() ? paginas(join(carpeta, e.name)) : e.name.endsWith(".html") ? [join(carpeta, e.name)] : []);
const resumen = (texto) => `'sha256-${createHash("sha256").update(texto, "utf8").digest("base64")}'`;

const faltan = { "script-src": new Set(), "style-src": new Set() };
const usados = { "script-src": new Set(), "style-src": new Set() };
const errores = [];
for (const archivo of paginas(DIST)) {
  const html = readFileSync(archivo, "utf8");
  for (const [, atributos, cuerpo] of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    if (/\bsrc=/.test(atributos)) continue;
    const r = resumen(cuerpo);
    usados["script-src"].add(r);
    if (!permitidos["script-src"].has(r)) faltan["script-src"].add(r);
  }
  for (const [, cuerpo] of html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)) {
    const r = resumen(cuerpo);
    usados["style-src"].add(r);
    if (!permitidos["style-src"].has(r)) faltan["style-src"].add(r);
  }
  if (/\sstyle="/.test(html)) errores.push(`${archivo}: atributo style="..." (requeriría 'unsafe-inline')`);
  if (/\son[a-z]+="/.test(html)) errores.push(`${archivo}: manejador en línea on...= (requeriría 'unsafe-hashes')`);
}
for (const d of ["script-src", "style-src"]) {
  if (permitidos[d].has("'unsafe-inline'")) errores.push(`${d} no debe incluir 'unsafe-inline'`);
  if (faltan[d].size) {
    errores.push(`${d} de vercel.json no autoriza: ${[...faltan[d]].join(" ")}`);
  }
}
if (errores.length) {
  console.error("La política de seguridad de contenidos no coincide con el sitio compilado:");
  errores.forEach((e) => console.error(`  - ${e}`));
  console.error("\nDirectivas que corresponden a esta compilación:");
  for (const d of ["script-src", "style-src"]) console.error(`  ${d} 'self' ${[...usados[d]].join(" ")}`);
  process.exit(1);
}
console.log(`CSP verificada: ${usados["script-src"].size} scripts y ${usados["style-src"].size} ` +
  "estilos en línea, todos autorizados por su resumen SHA-256.");
