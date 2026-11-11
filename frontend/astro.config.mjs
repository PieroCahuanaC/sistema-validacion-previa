// Capa de presentación: sitio estático (Vercel) que consume la API REST del backend (Render).
// El navegador llama siempre a /api del mismo sitio: en Vercel, vercel.json reenvía /api/* a la
// API, y en desarrollo lo hace el proxy de Vite. Así las cookies de sesión son del mismo sitio
// y pueden ser SameSite=Strict (Tabla 13 de la Práctica 5).
import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";

const API_LOCAL = process.env.API_LOCAL ?? "http://localhost:8000";
const proxy = { "/api": { target: API_LOCAL, changeOrigin: false } };

export default defineConfig({
  integrations: [react()],
  vite: { plugins: [tailwindcss()], server: { proxy }, preview: { proxy } },
});
