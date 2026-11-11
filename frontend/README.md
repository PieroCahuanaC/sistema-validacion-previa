# Frontend — capa de presentación

Astro + React + Tailwind. Pantallas implementadas de la Práctica 7:

- Incremento 1: P03 (Registrar requerimiento, pasos 1 y 2) y P04 (Detalle del requerimiento y semáforo).
- Incremento 2: P01 (Iniciar sesión y cambio de contraseña temporal), P02 (Inicio con menú según
  rol, tarjetas y «Pendientes de su acción») y P16 (Gestionar usuarios).
- Incremento 3, parte A: P05 (Aplicar ajuste sugerido), P07 (Historial de trazabilidad), P08
  (Bandeja de aprobación), P11 (Panel de alertas) y P17 (Mis requerimientos); la P04 suma
  Subsanar y reenviar, Anular y Ver historial.

```bash
npm install
npm run dev                 # http://localhost:4321 (con el backend en http://localhost:8000)
```

El navegador llama siempre a `/api` del mismo sitio. En desarrollo lo reenvía el proxy de Vite
(`astro.config.mjs`) y en Vercel la regla de `vercel.json`, de modo que las cookies de sesión
(HttpOnly, Secure, SameSite=Strict) pertenecen al dominio del frontend y nunca se guardan en el
almacenamiento del navegador.
