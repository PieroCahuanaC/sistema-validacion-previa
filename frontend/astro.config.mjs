// Capa de presentación: sitio estático (Vercel) que consume la API REST del backend (Render).
import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  integrations: [react()],
  vite: { plugins: [tailwindcss()] },
});
