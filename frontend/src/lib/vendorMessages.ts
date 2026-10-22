/**
 * Gotowe wiadomości do usługodawców (do skopiowania i wysłania samodzielnie — aplikacja nic nie wysyła).
 * Teksty uzupełniamy danymi wesela; czego nie znamy, zostawiamy w nawiasach kwadratowych do wpisania.
 */

export type MessageKind = "inquiry" | "booking" | "contract" | "dayInfo" | "thanks";

export interface MessageContext {
  vendorName: string;
  category: string;
  weddingDate: string | null; // „17 czerwca 2028” albo „czerwiec 2028”
  city: string | null;
  guests: number | null;
  ceremony: string | null; // „kościelny”, „cywilny”…
  signature: string | null; // podpis pary
}

export const MESSAGE_KINDS: { id: MessageKind; label: string }[] = [
  { id: "inquiry", label: "Zapytanie o termin i ofertę" },
  { id: "booking", label: "Rezerwacja terminu" },
  { id: "contract", label: "Prośba o umowę i harmonogram płatności" },
  { id: "dayInfo", label: "Ustalenia na dzień ślubu" },
  { id: "thanks", label: "Podziękowanie po weselu" },
];

/** Zdanie o tym, czego szukamy — zależnie od rodzaju usługodawcy. */
function need(c: MessageContext): string {
  const guests = c.guests ? `ok. ${c.guests} gości` : "[liczba] gości";
  switch (c.category) {
    case "venue":
    case "catering":
      return `Szukamy sali z obiadem i kolacją dla ${guests}. Prosimy o menu z cenami za osobę, cenę dla dzieci, minimalną liczbę gości oraz informację, co jest wliczone (napoje, tort, obsługa, nocleg dla pary).`;
    case "photographer":
    case "videographer":
      return "Interesuje nas reportaż od przygotowań do oczepin. Prosimy o pakiety, termin oddania materiału i informację o dojeździe.";
    case "dj":
    case "band":
    case "musician":
      return `Szukamy oprawy muzycznej na wesele dla ${guests}, zwykle od ok. 17:00 do 4:00. Prosimy o cenę, skład i informację, czy prowadzicie zabawy i oczepiny.`;
    case "makeup":
    case "hairdresser":
      return "Prosimy o cenę dla Panny Młodej (z próbą) i dodatkowych osób oraz informację, czy dojeżdżacie na miejsce przygotowań.";
    case "transport":
      return "Potrzebujemy przewozu gości między kościołem/USC a salą oraz powrotów w nocy. Prosimy o wycenę.";
    default:
      return "Prosimy o ofertę z cenami i informację o dostępności.";
  }
}

export function messageText(kind: MessageKind, c: MessageContext): string {
  const date = c.weddingDate ?? "[data ślubu]";
  const where = c.city ? ` w okolicy: ${c.city}` : "";
  const sign = c.signature ?? "[Wasze imiona]";
  const hello = `Dzień dobry,`;
  switch (kind) {
    case "inquiry":
      return [
        hello,
        "",
        `planujemy ślub${c.ceremony ? ` ${c.ceremony}` : ""} i wesele: ${date}${where}. Czy ten termin jest u Państwa wolny?`,
        need(c),
        "",
        "Będziemy wdzięczni za ofertę w PDF lub e-mailu.",
        "",
        "Pozdrawiamy,",
        sign,
      ].join("\n");
    case "booking":
      return [
        hello,
        "",
        `dziękujemy za ofertę — chcemy zarezerwować termin ${date}. Prosimy o potwierdzenie rezerwacji oraz informację o wysokości i terminie zadatku (lub zaliczki) i numerze konta.`,
        "",
        "Pozdrawiamy,",
        sign,
      ].join("\n");
    case "contract":
      return [
        hello,
        "",
        `prosimy o przesłanie projektu umowy na ${date}. Zależy nam, żeby w umowie były: dokładny zakres usługi i cena, harmonogram płatności (zadatek czy zaliczka), zasady zmiany liczby gości lub godzin, waloryzacja ceny oraz warunki odwołania.`,
        "",
        "Pozdrawiamy,",
        sign,
      ].join("\n");
    case "dayInfo":
      return [
        hello,
        "",
        `zbliża się nasz ślub (${date}). Chcielibyśmy potwierdzić: godzinę przyjazdu, osobę kontaktową w dniu ślubu i numer telefonu oraz to, czego Państwo od nas potrzebują (np. posiłek dla ekipy, miejsce parkingowe, gniazdko).`,
        "Aktualny program dnia prześlemy linkiem z aplikacji — prosimy o potwierdzenie, że jest czytelny.",
        "",
        "Pozdrawiamy,",
        sign,
      ].join("\n");
    case "thanks":
      return [
        hello,
        "",
        `bardzo dziękujemy za pracę na naszym weselu (${date}). Wszystko się udało, a goście jeszcze o tym mówią!`,
        "Chętnie zostawimy opinię — prosimy o link, pod którym możemy ją dodać.",
        "",
        "Serdecznie pozdrawiamy,",
        sign,
      ].join("\n");
  }
}

/** Temat wiadomości (e-mail). */
export function messageSubject(kind: MessageKind, c: MessageContext): string {
  const date = c.weddingDate ?? "termin do ustalenia";
  const label = MESSAGE_KINDS.find((k) => k.id === kind)?.label ?? "Wesele";
  return `${label} — wesele ${date}`;
}
