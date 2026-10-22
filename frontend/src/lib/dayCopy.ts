/**
 * Kopia programu dnia na tym urządzeniu — na wypadek braku zasięgu w dniu ślubu.
 *
 * Service worker nigdy nie buforuje /api/* (dane osobowe). Zamiast tego jawny, wąski zapis
 * w localStorage: tylko tytuły, godziny, miejsca, plan B, przygotowania i nazwy usługodawców —
 * bez gości, diet i kwot. Kopia wygasa dzień po ślubie i znika przy wylogowaniu.
 */

export interface DayCopyItem {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  location: string | null;
  plan_b: string | null;
  preparations: string | null;
  vendor_name: string | null;
}

export interface DayCopy {
  /** Nazwa wesela (nagłówek na ekranie bez sieci). */
  name: string;
  /** Data ślubu (RRRR-MM-DD) — kopia wygasa następnego dnia. */
  wedding_date: string | null;
  saved_at: string;
  items: DayCopyItem[];
}

const PREFIX = "wp-day-copy:";
/** Bez daty ślubu kopia żyje tydzień od zapisu. */
const NO_DATE_TTL_DAYS = 7;

export const weddingCopyKey = (weddingId: string) => `w:${weddingId}`;
/** Strona usługodawcy: klucz z początku tokenu (pełny token nie jest potrzebny do dopasowania). */
export const publicCopyKey = (token: string) => `t:${token.slice(0, 12)}`;

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Dzień po ślubie (albo tydzień od zapisu) — po tej dacie kopii nie pokazujemy i ją usuwamy. */
export function isExpired(copy: DayCopy, today: string): boolean {
  if (copy.wedding_date) return today > addDays(copy.wedding_date, 1);
  return today > addDays(copy.saved_at.slice(0, 10), NO_DATE_TTL_DAYS);
}

function addDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, (d ?? 1) + days)).toISOString().slice(0, 10);
}

export function saveDayCopy(key: string, copy: Omit<DayCopy, "saved_at">, now = new Date()): DayCopy | null {
  const full: DayCopy = {
    ...copy,
    saved_at: now.toISOString(),
    // Tylko pola z listy — nawet jeśli wywołujący przekaże więcej.
    items: copy.items.map((i) => ({
      id: i.id,
      title: i.title,
      starts_at: i.starts_at,
      ends_at: i.ends_at,
      location: i.location,
      plan_b: i.plan_b,
      preparations: i.preparations,
      vendor_name: i.vendor_name,
    })),
  };
  try {
    storage()?.setItem(PREFIX + key, JSON.stringify(full));
    return full;
  } catch {
    return null; // pełna pamięć albo tryb prywatny: bez kopii
  }
}

export function readDayCopy(key: string, today: string): DayCopy | null {
  const s = storage();
  if (!s) return null;
  try {
    const raw = s.getItem(PREFIX + key);
    if (!raw) return null;
    const copy = JSON.parse(raw) as DayCopy;
    if (!Array.isArray(copy.items) || isExpired(copy, today)) {
      s.removeItem(PREFIX + key);
      return null;
    }
    return copy;
  } catch {
    return null;
  }
}

export function removeDayCopy(key: string): void {
  try {
    storage()?.removeItem(PREFIX + key);
  } catch {
    // brak dostępu do pamięci — nic do usunięcia
  }
}

/** Kopie z kont (wesela) aktualne na dziś — do ekranu „Brak połączenia”. */
export function listWeddingCopies(today: string): DayCopy[] {
  const s = storage();
  if (!s) return [];
  const keys: string[] = [];
  for (let i = 0; i < s.length; i++) {
    const k = s.key(i);
    if (k?.startsWith(`${PREFIX}w:`)) keys.push(k.slice(PREFIX.length));
  }
  return keys.map((k) => readDayCopy(k, today)).filter((c): c is DayCopy => c !== null);
}

/** Wylogowanie: usuwamy wszystkie kopie programu z tego urządzenia. */
export function clearDayCopies(): void {
  const s = storage();
  if (!s) return;
  try {
    const keys: string[] = [];
    for (let i = 0; i < s.length; i++) {
      const k = s.key(i);
      if (k?.startsWith(PREFIX)) keys.push(k);
    }
    keys.forEach((k) => s.removeItem(k));
  } catch {
    // brak dostępu do pamięci
  }
}
