/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// API pod tym samym adresem co aplikacja (proxy w dev, Caddy w produkcji):
// ciasteczko sesji ma SameSite=Strict i ścieżkę /api/v1/auth, więc musi to być ten sam origin.
const API = process.env.WP_API_URL ?? "http://127.0.0.1:8010";
// Testy E2E uruchamiają własny serwer na innych portach (osobne API i baza, zob. playwright.config.ts).
const DEV_PORT = Number(process.env.WP_WEB_PORT ?? 5173);
const PREVIEW_PORT = Number(process.env.WP_PREVIEW_PORT ?? 4173);

// Ta sama polityka co w deploy/Caddyfile: testy E2E na buildzie (E2E_PROD=1) sprawdzają,
// że aplikacja działa bez skryptów inline. Atrybuty style (React Aria) wymagają style-src-attr.
// React Aria wstrzykuje dwa stałe bloki <style> (dotyk na iOS, blokada przewijania pod panelem):
// dopuszczamy dokładnie je przez skróty, bez 'unsafe-inline'. Zmiana biblioteki → test CSP to wykaże.
export const STYLE_HASHES = [
  "'sha256-38RhXrc7EdReTKsOm23ZPOCUgniTUUcjky8QOOrQx6o='", // usePress (touch-action)
  "'sha256-gYiS/BvZvRcK27JIXTuwhZ3hs2+VJ1X+2gUlE+farlg='", // usePreventScroll (iOS, otwarty panel)
];
export const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  `style-src 'self' ${STYLE_HASHES.join(" ")}`,
  "style-src-attr 'unsafe-inline'",
  "font-src 'self'",
  "img-src 'self' data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

export default defineConfig({
  plugins: [react()],
  server: {
    port: DEV_PORT,
    strictPort: true,
    proxy: {
      "/api": { target: API, changeOrigin: false },
      "/health": { target: API, changeOrigin: false },
    },
  },
  preview: {
    port: PREVIEW_PORT,
    strictPort: true,
    headers: { "Content-Security-Policy": CSP },
    proxy: {
      "/api": { target: API, changeOrigin: false },
      "/health": { target: API, changeOrigin: false },
    },
  },
  build: {
    target: "es2022",
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: true,
  },
});
