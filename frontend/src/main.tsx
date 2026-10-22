// Fonty z własnego serwera (licencja OFL); przeglądarka pobiera tylko używane kroje i zakresy znaków.
import "@fontsource-variable/dm-sans/wght.css";
import "@fontsource-variable/lora/wght.css";
import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/bodoni-moda/wght.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./lib/preferences";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";

const root = document.getElementById("root");
if (!root) throw new Error("Brak elementu #root");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Instalowalna aplikacja (PWA): tylko w buildzie produkcyjnym; serwer deweloperski działa bez cache.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
