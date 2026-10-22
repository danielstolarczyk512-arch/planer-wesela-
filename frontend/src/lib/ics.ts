/**
 * Plik kalendarza (iCalendar, RFC 5545) z wydarzeniem — tworzony w przeglądarce gościa.
 * Bez nowych adresów publicznych: dane są już na stronie z linkiem RSVP.
 */

export interface IcsEvent {
  uid: string;
  title: string;
  startsAt: string;
  endsAt?: string | null;
  location?: string | null;
  description?: string | null;
}

const DEFAULT_HOURS = 6; // wesele bez godziny końca: blok 6 h w kalendarzu

function stamp(iso: string): string {
  return new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

/** Ucieczka tekstu wg RFC 5545: \\ ; , i nowe linie. */
export function escapeText(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

/** Zawijanie wierszy do 75 bajtów (RFC 5545 §3.1) — tu uproszczone do 73 znaków. */
function fold(line: string): string {
  const parts: string[] = [];
  for (let i = 0; i < line.length; i += 73) parts.push((i ? " " : "") + line.slice(i, i + 73));
  return parts.join("\r\n");
}

export function buildIcs(events: IcsEvent[], now = new Date()): string {
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Nasz dzien//PL", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"];
  for (const e of events) {
    const end = e.endsAt ?? new Date(new Date(e.startsAt).getTime() + DEFAULT_HOURS * 3_600_000).toISOString();
    lines.push(
      "BEGIN:VEVENT",
      `UID:${e.uid}@nasz-dzien`,
      `DTSTAMP:${stamp(now.toISOString())}`,
      `DTSTART:${stamp(e.startsAt)}`,
      `DTEND:${stamp(end)}`,
      fold(`SUMMARY:${escapeText(e.title)}`),
    );
    if (e.location) lines.push(fold(`LOCATION:${escapeText(e.location)}`));
    if (e.description) lines.push(fold(`DESCRIPTION:${escapeText(e.description)}`));
    lines.push("END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.join("\r\n") + "\r\n";
}

export function downloadIcs(events: IcsEvent[], filename: string): void {
  const url = URL.createObjectURL(new Blob([buildIcs(events)], { type: "text/calendar;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
