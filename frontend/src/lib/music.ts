/** Momenty wesela dla listy muzyki — wspólne dla ekranu pary i linku DJ-a (bez zależności od ekranów). */
import type { components } from "../api/schema";

export type Moment = components["schemas"]["MusicOut"]["moment"];

export const MOMENTS: { id: Moment; label: string }[] = [
  { id: "ceremony", label: "Ceremonia" },
  { id: "entrance", label: "Wejście pary na salę" },
  { id: "first_dance", label: "Pierwszy taniec" },
  { id: "parents", label: "Podziękowania dla rodziców" },
  { id: "cake", label: "Tort" },
  { id: "oczepiny", label: "Oczepiny" },
  { id: "last_dance", label: "Ostatni taniec" },
  { id: "must", label: "Koniecznie zagrajcie" },
  { id: "avoid", label: "Nie grać" },
  { id: "other", label: "Inne" },
];

/** „Perfect — Ed Sheeran”. */
export function songLabel(e: { title: string; artist?: string | null }): string {
  return e.artist ? `${e.title} — ${e.artist}` : e.title;
}

/** Utwory pogrupowane w kolejności momentów (puste momenty pominięte). */
export function byMoment<T extends { moment: Moment }>(entries: T[]): { id: Moment; label: string; items: T[] }[] {
  return MOMENTS.map((m) => ({ ...m, items: entries.filter((e) => e.moment === m.id) })).filter((m) => m.items.length > 0);
}
