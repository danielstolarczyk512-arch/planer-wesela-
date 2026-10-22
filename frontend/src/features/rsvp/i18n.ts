/**
 * Wersja językowa strony gościa (plan C2): polski i angielski — dla gości z zagranicy.
 * Domyślnie polski; przeglądarka w innym języku → angielski. Wybór gościa zapamiętany na urządzeniu.
 * Tłumaczymy interfejs; treści wpisane przez parę (powitanie, dojazd, nazwy wydarzeń) zostają jak są.
 */
import { createContext, useContext } from "react";

export type Lang = "pl" | "en";
const KEY = "wp-rsvp-lang";
const TIME_ZONE = "Europe/Warsaw";

const pl = {
  brand: "Nasz dzień",
  invitation: "Zaproszenie",
  linkBroken: "Link nie działa",
  linkExpired: "Ten link jest nieprawidłowy albo wygasł. Poproście parę młodą o nowy.",
  tooMany: "Zbyt wiele otwarć strony w krótkim czasie. Spróbujcie ponownie za kilka minut.",
  thanks: "Dziękujemy!",
  delivered: "Odpowiedź dotarła do pary młodej.",
  seeYou: (names: string) => `Do zobaczenia: ${names}.`,
  sorry: "Szkoda, że nie możecie być z nami.",
  changeAnswer: "Zmień odpowiedź",
  deadline: (date: string) => `Prosimy o odpowiedź do ${date}.`,
  noDeadline: "Prosimy o odpowiedź — możecie ją później zmienić tym samym linkiem.",
  noEvents: "Para młoda jeszcze uzupełnia szczegóły uroczystości. Zajrzyjcie tu ponownie za kilka dni.",
  closed: "Termin odpowiedzi minął. Jeśli coś się zmieniło, skontaktujcie się z parą młodą.",
  events: "Wydarzenia",
  showMap: "Pokaż na mapie",
  addToCalendar: "Dodaj do kalendarza",
  plan: "Plan dnia",
  willYouCome: "Czy będziesz?",
  answers: { attending: "Będę", declined: "Nie będę", maybe: "Jeszcze nie wiem" },
  diet: "Dieta",
  diets: { standard: "Bez wymagań", vegetarian: "Wegetariańska", vegan: "Wegańska", gluten_free: "Bezglutenowa", other: "Inna (opisz)" },
  kitchenNotes: "Uwagi dla kuchni (opcjonalnie)",
  notesKnown: "Para młoda ma już Twoje uwagi. Wpisz nowe tylko, jeśli coś się zmieniło.",
  notesHint: "Np. alergia na orzechy. Wpisz tylko to, co potrzebne kuchni.",
  needStay: "Potrzebuję noclegu",
  needTransport: "Potrzebuję transportu",
  runs: "Przejazd zorganizowany przez parę",
  rides: "Przejazdy",
  ridesHint: "Miejsce zarezerwujesz w formularzu poniżej (zaznacz „Potrzebuję transportu”).",
  runsHint: "Zaznacz kursy, którymi pojedziesz. Miejsca są ograniczone.",
  seatsLeft: (n: number) => (n === 0 ? "brak miejsc" : n === 1 ? "1 wolne miejsce" : n < 5 ? `${n} wolne miejsca` : `${n} wolnych miejsc`),
  consent:
    "Zgadzam się, aby para młoda i obsługa wesela przetwarzały podane uwagi dietetyczne (mogą dotyczyć zdrowia) wyłącznie w celu przygotowania posiłków. Zgodę można wycofać, pisząc do pary młodej.",
  pickOne: "Zaznaczcie odpowiedź przynajmniej dla jednej osoby.",
  previewOnly: "To podgląd — goście wyślą tu odpowiedź ze swojego linku.",
  needConsent: "Aby wysłać uwagi dla kuchni, zaznaczcie zgodę pod formularzem.",
  send: (n: number) => (n === 0 ? "Wyślij odpowiedź" : n === 1 ? "Wyślij 1 odpowiedź" : `Wyślij ${n} odpowiedzi`),
  info: "Informacje dla gości",
  infoLabels: {
    directions: "Dojazd i parking",
    accommodation: "Nocleg",
    transport: "Transport",
    dress_code: "Dress code",
    gifts: "Prezenty",
    contact: "Kontakt w dniu ślubu",
  },
  addCompanion: "Dodaj osobę towarzyszącą",
  companion: "Osoba towarzysząca",
  firstName: "Imię",
  lastName: "Nazwisko (opcjonalnie)",
  age: "Wiek",
  ages: { adult: "Dorosły", teen: "Nastolatek (13–17)", child: "Dziecko (4–12)", infant: "Maluch (0–3)" },
  companionHint: "Po dodaniu zaznaczcie poniżej, czy ta osoba będzie, i wyślijcie odpowiedź.",
  add: "Dodaj",
  cancel: "Anuluj",
  remove: "Usuń",
  removeLabel: (name: string) => `Usuń: ${name}`,
  privacy: "",
  language: "Język strony",
  giftsTitle: "Lista prezentów",
  giftsHint: "Wybierzcie prezent, żeby nikt nie kupił tego samego. Inni goście zobaczą tylko, że jest zarezerwowany.",
  giftReserve: "Wybieramy ten",
  giftRelease: "Rezygnuję",
  giftReserved: "zarezerwowany",
  giftMine: "Wasz wybór",
  giftFund: "Wkład do wspólnego celu — bez rezerwacji",
  giftShop: "Zobacz w sklepie",
  announcement: "Wiadomość od pary",
  tablesTitle: "Gdzie siedzicie",
  seat: (n: number) => `miejsce ${n}`,
  wishesTitle: "Księga życzeń",
  wishesHint: "Zostawcie parze kilka słów — przeczytają je po weselu.",
  wishAuthor: "Podpis",
  wishText: "Życzenia",
  wishSend: "Zostaw życzenia",
  wishThanks: "Dziękujemy! Życzenia trafiły do pary.",
  wishesMine: "Wasze wpisy",
  wishesFull: "Dziękujemy za wszystkie wpisy!",
  menuTitle: "Menu",
  menuNote: "Alergeny według informacji sali. Masz alergię? Napisz o niej w uwagach przy swoim imieniu.",
  songsTitle: "Piosenka na parkiet",
  songsHint: (n: number) => `Zaproponujcie utwór, przy którym ruszycie do tańca (najwyżej ${n}). Para zdecyduje, co zagra DJ.`,
  songTitle: "Tytuł utworu",
  songArtist: "Wykonawca (opcjonalnie)",
  songSend: "Zaproponuj",
  songsMine: "Wasze propozycje",
  songsFull: "Wykorzystaliście wszystkie propozycje — dziękujemy!",
  songThanks: "Dziękujemy! Propozycja trafiła do pary.",
  textSize: "Wielkość tekstu",
  textNormal: "Zwykły",
  textLarge: "Większy",
  at: "godz.",
};

export type Strings = typeof pl;

const en: Strings = {
  brand: "Nasz dzień",
  invitation: "Invitation",
  linkBroken: "This link does not work",
  linkExpired: "This link is invalid or has expired. Please ask the couple for a new one.",
  tooMany: "Too many visits in a short time. Please try again in a few minutes.",
  thanks: "Thank you!",
  delivered: "Your reply has reached the couple.",
  seeYou: (names: string) => `See you soon: ${names}.`,
  sorry: "We are sorry you cannot join us.",
  changeAnswer: "Change your reply",
  deadline: (date: string) => `Please reply by ${date}.`,
  noDeadline: "Please reply — you can change it later using the same link.",
  noEvents: "The couple is still adding the details. Please check back in a few days.",
  closed: "The reply deadline has passed. If something has changed, please contact the couple.",
  events: "Events",
  showMap: "Show on map",
  addToCalendar: "Add to calendar",
  plan: "Schedule",
  willYouCome: "Will you come?",
  answers: { attending: "Yes", declined: "No", maybe: "Not sure yet" },
  diet: "Diet",
  diets: { standard: "No requirements", vegetarian: "Vegetarian", vegan: "Vegan", gluten_free: "Gluten-free", other: "Other (describe)" },
  kitchenNotes: "Notes for the kitchen (optional)",
  notesKnown: "The couple already has your notes. Enter new ones only if something has changed.",
  notesHint: "E.g. nut allergy. Only what the kitchen needs to know.",
  needStay: "I need accommodation",
  needTransport: "I need transport",
  runs: "Transport arranged by the couple",
  rides: "Rides",
  ridesHint: "Book a seat in the form below (tick “I need transport”).",
  runsHint: "Tick the rides you will take. Seats are limited.",
  seatsLeft: (n: number) => (n === 0 ? "full" : n === 1 ? "1 seat left" : `${n} seats left`),
  consent:
    "I agree that the couple and the wedding staff may process these dietary notes (they may concern health) only to prepare meals. I can withdraw consent by writing to the couple.",
  pickOne: "Please choose a reply for at least one person.",
  previewOnly: "This is a preview — guests send their replies from their own link.",
  needConsent: "To send notes for the kitchen, please tick the consent below the form.",
  send: (n: number) => (n === 0 ? "Send reply" : n === 1 ? "Send 1 reply" : `Send ${n} replies`),
  info: "Information for guests",
  infoLabels: {
    directions: "Getting there and parking",
    accommodation: "Accommodation",
    transport: "Transport",
    dress_code: "Dress code",
    gifts: "Gifts",
    contact: "Contact on the day",
  },
  addCompanion: "Add a plus-one",
  companion: "Plus-one",
  firstName: "First name",
  lastName: "Last name (optional)",
  age: "Age",
  ages: { adult: "Adult", teen: "Teenager (13–17)", child: "Child (4–12)", infant: "Toddler (0–3)" },
  companionHint: "After adding, choose below whether this person will come and send your reply.",
  add: "Add",
  cancel: "Cancel",
  remove: "Remove",
  removeLabel: (name: string) => `Remove: ${name}`,
  privacy: "The details in this form are visible only to the couple organising the wedding. They will be deleted after the wedding.",
  language: "Page language",
  giftsTitle: "Gift list",
  giftsHint: "Pick a gift so nobody buys the same one. Other guests will only see that it is taken.",
  giftReserve: "We'll get this",
  giftRelease: "Cancel my choice",
  giftReserved: "taken",
  giftMine: "Your choice",
  giftFund: "A contribution to a shared goal — no reservation needed",
  giftShop: "See in shop",
  announcement: "A message from the couple",
  tablesTitle: "Where you are seated",
  seat: (n: number) => `seat ${n}`,
  wishesTitle: "Guest book",
  wishesHint: "Leave the couple a few words — they will read them after the wedding.",
  wishAuthor: "Signed",
  wishText: "Your wishes",
  wishSend: "Leave wishes",
  wishThanks: "Thank you! The couple has received your wishes.",
  wishesMine: "Your entries",
  wishesFull: "Thank you for all your entries!",
  menuTitle: "Menu",
  menuNote: "Allergens as provided by the venue. Have an allergy? Mention it in the notes next to your name.",
  songsTitle: "A song for the dance floor",
  songsHint: (n: number) => `Suggest a song that gets you dancing (up to ${n}). The couple will decide what the DJ plays.`,
  songTitle: "Song title",
  songArtist: "Artist (optional)",
  songSend: "Suggest",
  songsMine: "Your suggestions",
  songsFull: "You have used all your suggestions — thank you!",
  songThanks: "Thank you! The couple has received your suggestion.",
  textSize: "Text size",
  textNormal: "Normal",
  textLarge: "Larger",
  at: "at",
};

export const STRINGS: Record<Lang, Strings> = { pl, en };

/** Wybór gościa zapamiętany na urządzeniu (pierwszeństwo przed językiem zaproszenia). */
export function savedLang(): Lang | null {
  try {
    const saved = window.localStorage.getItem(KEY);
    if (saved === "pl" || saved === "en") return saved;
  } catch {
    // brak dostępu do pamięci
  }
  return null;
}

export function browserLang(): Lang {
  return navigator.language.toLowerCase().startsWith("pl") ? "pl" : "en";
}

/** Kolejność: wybór gościa → język zaproszenia (od pary) → język przeglądarki. */
export function pickLang(saved: Lang | null, invitation: Lang | null | undefined): Lang {
  return saved ?? invitation ?? browserLang();
}

export function initialLang(): Lang {
  return savedLang() ?? browserLang();
}

const READABLE_KEY = "wp-rsvp-readable";

/** Tryb czytelny (większy tekst, mocniejszy kontrast) zapamiętany na urządzeniu gościa. */
export function savedReadable(): boolean {
  try {
    return window.localStorage.getItem(READABLE_KEY) === "1";
  } catch {
    return false;
  }
}

export function saveReadable(on: boolean): void {
  try {
    if (on) window.localStorage.setItem(READABLE_KEY, "1");
    else window.localStorage.removeItem(READABLE_KEY);
  } catch {
    // wybór działa do przeładowania
  }
}

export function saveLang(lang: Lang): void {
  try {
    window.localStorage.setItem(KEY, lang);
  } catch {
    // wybór działa do przeładowania
  }
}

const LOCALE: Record<Lang, string> = { pl: "pl-PL", en: "en-GB" };

/** Data (RRRR-MM-DD) słownie w danym języku, np. „17 czerwca 2028” / „17 June 2028”. */
export function dateIn(lang: Lang, isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat(LOCALE[lang], { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1, 12)),
  );
}

export function timeIn(lang: Lang, iso: string): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { hour: "2-digit", minute: "2-digit", timeZone: TIME_ZONE }).format(new Date(iso));
}

/** Kiedy wydarzenie: data i godzina w czasie polskim. */
export function whenIn(lang: Lang, startsAt: string | null | undefined): string | null {
  if (!startsAt) return null;
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(new Date(startsAt));
  return `${dateIn(lang, day)}, ${STRINGS[lang].at} ${timeIn(lang, startsAt)}`;
}

export const LangContext = createContext<Lang>("pl");

export function useT(): Strings {
  return STRINGS[useContext(LangContext)];
}

export function useLang(): Lang {
  return useContext(LangContext);
}
