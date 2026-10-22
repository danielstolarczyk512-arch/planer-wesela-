/**
 * Kolejka przesunięć programu dnia zrobionych bez sieci (plan dalszej pracy C2).
 *
 * Koordynator przesuwa program („+15 min”) bez zasięgu: przesunięcie trafia do kolejki
 * w localStorage i od razu zmienia godziny na ekranie (oraz w kopii programu). Po powrocie sieci
 * kolejka wysyła się sama — ale tylko wtedy, gdy punkt, od którego przesuwano, ma na serwerze
 * tę samą godzinę co w chwili przesunięcia. Jeśli ktoś w międzyczasie zmienił program, nic nie
 * wysyłamy automatycznie: koordynator decyduje („Wyślij mimo to” / „Odrzuć”).
 * Kolejka znika przy wylogowaniu (razem z kopią programu).
 */

export interface QueuedShift {
  id: string;
  from_item_id: string;
  from_title: string;
  minutes: number;
  /** Godzina punktu na serwerze w chwili przesunięcia (wykrywanie zmian w międzyczasie). */
  base_starts_at: string;
  queued_at: string;
}

export interface ShiftableItem {
  id: string;
  starts_at: string;
  ends_at: string;
}

const PREFIX = "wp-day-queue:";

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readQueue(weddingId: string): QueuedShift[] {
  try {
    const raw = storage()?.getItem(PREFIX + weddingId);
    const list = raw ? (JSON.parse(raw) as QueuedShift[]) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function write(weddingId: string, list: QueuedShift[]): void {
  try {
    if (list.length) storage()?.setItem(PREFIX + weddingId, JSON.stringify(list));
    else storage()?.removeItem(PREFIX + weddingId);
  } catch {
    // brak pamięci / tryb prywatny: kolejka działa tylko do przeładowania
  }
}

/**
 * Dodaje przesunięcie. `base_starts_at` = godzina punktu w programie z serwera PO zastosowaniu
 * wcześniejszych przesunięć z kolejki (`applyQueue(serwer, kolejka)`): przy wysyłaniu po kolei
 * serwer będzie ją miał dokładnie wtedy, gdy nikt inny nie zmienił programu.
 */
export function enqueueShift(weddingId: string, shift: Omit<QueuedShift, "id" | "queued_at">, now = new Date()): QueuedShift[] {
  const list = [...readQueue(weddingId), { ...shift, id: `${now.getTime()}-${Math.random().toString(36).slice(2, 7)}`, queued_at: now.toISOString() }];
  write(weddingId, list);
  return list;
}

export function removeShift(weddingId: string, id: string): QueuedShift[] {
  const list = readQueue(weddingId).filter((s) => s.id !== id);
  write(weddingId, list);
  return list;
}

export function clearQueues(): void {
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

const MIN = 60_000;
const shiftIso = (iso: string, minutes: number) => new Date(new Date(iso).getTime() + minutes * MIN).toISOString();

/**
 * Program po zastosowaniu kolejki (jak na serwerze: przesuwa się punkt i wszystko, co zaczyna się
 * o tej samej godzinie lub później). Kolejne przesunięcia działają na wyniku poprzednich.
 */
export function applyQueue<T extends ShiftableItem>(items: T[], queue: QueuedShift[]): T[] {
  let current = items;
  for (const q of queue) {
    const anchor = current.find((i) => i.id === q.from_item_id);
    if (!anchor) continue; // punkt usunięty: przesunięcie bez skutku
    const from = new Date(anchor.starts_at).getTime();
    current = current.map((i) =>
      new Date(i.starts_at).getTime() >= from ? { ...i, starts_at: shiftIso(i.starts_at, q.minutes), ends_at: shiftIso(i.ends_at, q.minutes) } : i,
    );
  }
  return [...current].sort((a, b) => a.starts_at.localeCompare(b.starts_at));
}

/** Czy przesunięcie można wysłać bez pytania: punkt istnieje i ma tę samą godzinę co przy przesuwaniu. */
export function canSendSafely(q: QueuedShift, serverItems: ShiftableItem[]): boolean {
  const item = serverItems.find((i) => i.id === q.from_item_id);
  return !!item && new Date(item.starts_at).getTime() === new Date(q.base_starts_at).getTime();
}
