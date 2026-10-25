import { useSyncExternalStore } from "react";

/** Preferencje wyglądu na urządzeniu (nie są danymi osobowymi wrażliwymi). */
export type ThemeMode = "romantic" | "system" | "light" | "dark" | "gold";

/** Style do wyboru (ustawienia, panel wyglądu). Romantyczny jest domyślny i podąża za trybem ciemnym systemu. */
export const THEME_OPTIONS: { value: ThemeMode; label: string }[] = [
  { value: "romantic", label: "Romantyczny" },
  { value: "system", label: "Systemowy" },
  { value: "light", label: "Ciepły beż" },
  { value: "dark", label: "Ciemna elegancja" },
  { value: "gold", label: "Biel i złoto" },
];

interface Preferences {
  theme: ThemeMode;
  reduceMotion: boolean;
}

const listeners = new Set<() => void>();

function read(): Preferences {
  let theme: ThemeMode = "romantic";
  let reduceMotion = false;
  try {
    const t = localStorage.getItem("wp.theme");
    if (t === "system" || t === "light" || t === "dark" || t === "gold") theme = t;
    reduceMotion = localStorage.getItem("wp.reduceMotion") === "1";
  } catch {
    // tryb prywatny: domyślne
  }
  return { theme, reduceMotion };
}

let current = read();

function apply(p: Preferences) {
  const root = document.documentElement;
  // Zmiana atrybutu, bez przeładowania i ponownego montowania: fokus i wpisany tekst zostają.
  root.dataset.theme = p.theme;
  root.classList.toggle("reduce-motion", p.reduceMotion);
}

function save(p: Preferences) {
  current = p;
  try {
    if (p.theme === "romantic") localStorage.removeItem("wp.theme");
    else localStorage.setItem("wp.theme", p.theme);
    if (p.reduceMotion) localStorage.setItem("wp.reduceMotion", "1");
    else localStorage.removeItem("wp.reduceMotion");
  } catch {
    // brak zapisu w trybie prywatnym: preferencja działa do zamknięcia karty
  }
  apply(p);
  listeners.forEach((l) => l());
}

export function setTheme(theme: ThemeMode) {
  const next = { ...current, theme };
  const doc = document as Document & { startViewTransition?: (update: () => void) => { finished: Promise<void> } };
  if (!doc.startViewTransition || motionReduced()) {
    save(next);
    return;
  }
  // Przenikanie kolorów (200 ms) zamiast skoku; stan formularzy zostaje (brak przemontowania).
  const root = document.documentElement;
  root.classList.add("theme-transition");
  doc
    .startViewTransition(() => save(next))
    .finished.finally(() => root.classList.remove("theme-transition"))
    .catch(() => undefined);
}

export function setReduceMotion(reduceMotion: boolean) {
  save({ ...current, reduceMotion });
}

export function usePreferences(): Preferences {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => current,
  );
}

/** Czy ruch ma być ograniczony (system albo ustawienie aplikacji). */
export function motionReduced(): boolean {
  return current.reduceMotion || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

apply(current);
