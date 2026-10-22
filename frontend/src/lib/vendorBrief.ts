/** Nazwy sekcji „informacji dla usługodawcy” zależne od rodzaju usługodawcy (edycja i strona linku). */
export interface BriefLabels {
  must: string;
  mustHint: string;
  avoid: string;
  people: string;
}

const MUSIC = ["dj", "band", "musician"];
const PHOTO = ["photographer", "videographer", "photobooth"];

export function briefLabels(category: string): BriefLabels {
  if (MUSIC.includes(category)) {
    return {
      must: "Utwory obowiązkowe",
      mustHint: "Np. pierwszy taniec, wejście pary, tort.",
      avoid: "Nie grać",
      people: "Kto jest kim (do zapowiedzi i zabaw)",
    };
  }
  if (PHOTO.includes(category)) {
    return {
      must: "Ujęcia obowiązkowe",
      mustHint: "Np. zdjęcie z dziadkami, cała rodzina Panny Młodej.",
      avoid: "Czego nie fotografować",
      people: "Kto jest kim (osoby do zdjęć)",
    };
  }
  if (category === "transport") {
    return { must: "Trasa i przystanki", mustHint: "Np. 15:00 dom Panny Młodej, 15:40 kościół.", avoid: "Czego unikać", people: "Kogo wieziecie" };
  }
  return { must: "Koniecznie", mustHint: "Rzeczy, o których usługodawca musi pamiętać.", avoid: "Czego unikać", people: "Kto jest kim" };
}

/** Lista „jedna pozycja w wierszu” → pozycje bez pustych wierszy (limit API: 40 × 200 znaków). */
export function linesToList(text: string): string[] {
  return text
    .split(String.fromCharCode(10))
    .map((l) => l.trim())
    .filter((l) => l !== "")
    .slice(0, 40)
    .map((l) => l.slice(0, 200));
}

/** „Babcia Halina — mama Pana Młodego” → osoba; wiersz bez myślnika to samo imię z rolą „gość”. */
export function linesToPeople(text: string): { name: string; role: string }[] {
  return linesToList(text).map((line) => {
    const at = ["—", " - ", ":"].map((sep) => [sep, line.indexOf(sep)] as const).find(([, i]) => i > 0);
    if (!at) return { name: line.slice(0, 80), role: "gość" };
    const [sep, i] = at;
    return { name: line.slice(0, i).trim().slice(0, 80), role: line.slice(i + sep.length).trim().slice(0, 120) || "gość" };
  });
}

export const peopleToLines = (people: { name: string; role: string }[]) => people.map((p) => `${p.name} — ${p.role}`).join(String.fromCharCode(10));
