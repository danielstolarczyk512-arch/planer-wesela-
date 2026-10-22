/** Ostatnio otwarte wesele na tym urządzeniu (sam identyfikator, bez danych osobowych). */
const KEY = "wp.lastWedding";

export function rememberWedding(id: string) {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    // tryb prywatny
  }
}

export function lastWedding(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function forgetWedding() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // tryb prywatny
  }
}
