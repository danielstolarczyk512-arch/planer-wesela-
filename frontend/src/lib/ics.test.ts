import { describe, expect, it } from "vitest";

import { buildIcs, escapeText } from "./ics";

// Ukośnik wsteczny składany w kodzie (narzędzia w tym repozytorium potrafią zgubić „\\” w literałach).
const BS = String.fromCharCode(92);
const CRLF = String.fromCharCode(13, 10);
const LF = String.fromCharCode(10);

describe("plik kalendarza dla gościa", () => {
  it("wydarzenie z czasem UTC, adresem i domyślnym końcem", () => {
    const ics = buildIcs(
      [{ uid: "e1", title: "Przyjęcie — Ania i Tomek", startsAt: "2028-06-17T15:00:00+02:00", location: "Dworek, ul. Lipowa 1; Kraków" }],
      new Date("2026-10-21T08:00:00Z"),
    );
    expect(ics.startsWith("BEGIN:VCALENDAR" + CRLF)).toBe(true);
    expect(ics).toContain("DTSTART:20280617T130000Z");
    expect(ics).toContain("DTEND:20280617T190000Z"); // bez godziny końca: 6 h
    expect(ics).toContain(`LOCATION:Dworek${BS}, ul. Lipowa 1${BS}; Kraków`);
    expect(ics).toContain("UID:e1@nasz-dzien");
    expect(ics.endsWith("END:VCALENDAR" + CRLF)).toBe(true);
  });

  it("koniec z danych i ucieczka znaków specjalnych", () => {
    const ics = buildIcs([{ uid: "e2", title: "A", startsAt: "2028-06-17T10:00:00Z", endsAt: "2028-06-17T11:30:00Z" }]);
    expect(ics).toContain("DTEND:20280617T113000Z");
    expect(escapeText(`a,b;c${BS}d${LF}e`)).toBe(`a${BS},b${BS};c${BS}${BS}d${BS}ne`);
  });
});
