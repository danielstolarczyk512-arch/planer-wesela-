/**
 * Formatowanie po polsku (GUI-SPEC v1.1, sekcja 2). Kwoty z API przychodzą jako napisy
 * ("37200.00"): nigdy nie zamieniamy ich na liczby zmiennoprzecinkowe do obliczeń.
 */

export const TIME_ZONE = "Europe/Warsaw";

export interface Money {
  amount: string;
  currency: string;
}

const moneyFormatters = new Map<string, Intl.NumberFormat>();

function moneyFormatter(currency: string, withCents: boolean): Intl.NumberFormat {
  const key = `${currency}:${withCents}`;
  let f = moneyFormatters.get(key);
  if (!f) {
    f = new Intl.NumberFormat("pl-PL", {
      style: "currency",
      currency,
      // Domyślnie pl-PL nie grupuje liczb 4-cyfrowych („5000 zł” obok „37 200 zł”).
      useGrouping: "always",
      minimumFractionDigits: withCents ? 2 : 0,
      maximumFractionDigits: withCents ? 2 : 0,
    });
    moneyFormatters.set(key, f);
  }
  return f;
}

/** "37200.00" → "37 200 zł"; "1250000.50" → "1 250 000,50 zł"; null → "Brak wyceny". */
export function formatMoney(value: Money | null | undefined, opts: { cents?: boolean } = {}): string {
  if (!value) return "Brak wyceny";
  if (!/^-?\d+(\.\d{1,2})?$/.test(value.amount)) throw new Error(`Nieprawidłowa kwota: ${value.amount}`);
  const hasCents = !/\.0*$/.test(value.amount) && value.amount.includes(".");
  // Intl przyjmuje napis dziesiętny bez utraty precyzji (Intl.NumberFormat v3).
  const amount = value.amount as unknown as number;
  return moneyFormatter(value.currency, opts.cents ?? hasCents).format(amount);
}

/** Pole kwoty: akceptuje przecinek lub kropkę i spacje; zwraca napis dla API albo null. */
export function parseAmountInput(raw: string): string | null {
  // \s obejmuje też twardą i wąską spację niełamiącą (separatory tysięcy z Intl).
  const cleaned = raw.replace(/\s/g, "").replace(/zł$/i, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const [whole = "0", frac = ""] = cleaned.split(".");
  return `${BigInt(whole).toString()}.${frac.padEnd(2, "0")}`;
}

const pluralRules = new Intl.PluralRules("pl-PL");

export type PluralForms = { one: string; few: string; many: string; other: string };

/** Forma zależna od liczby: plural(3, {one:"Zostało # zadanie", few:"Zostały # zadania", …}). */
export function plural(count: number, forms: PluralForms): string {
  const category = pluralRules.select(count) as keyof PluralForms;
  return (forms[category] ?? forms.other).replace("#", String(count));
}

const dateFormat = new Intl.DateTimeFormat("pl-PL", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: TIME_ZONE,
});
const timeFormat = new Intl.DateTimeFormat("pl-PL", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: TIME_ZONE,
});

/** "2028-07-01" (data kalendarzowa z API) → "1 lipca 2028". */
export function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  // Południe UTC: ta sama data kalendarzowa w Warszawie niezależnie od strefy urządzenia.
  return dateFormat.format(new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1, 12)));
}

/** Moment z API (z przesunięciem strefy) → "15:00" w czasie polskim. */
export function formatTime(isoDateTime: string): string {
  return timeFormat.format(new Date(isoDateTime));
}

/** Dzisiejsza data w Warszawie jako "YYYY-MM-DD" (nie data urządzenia za granicą). */
export function todayInWarsaw(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(now);
}

/** Różnica dni kalendarzowych (nie dzielenie milisekund przez 24 h). */
export function daysUntil(isoDate: string, now: Date = new Date()): number {
  const toUtc = (iso: string) => {
    const [y, m, d] = iso.split("-").map(Number);
    return Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1);
  };
  return Math.round((toUtc(isoDate) - toUtc(todayInWarsaw(now))) / 86_400_000);
}

/** Moment wydarzenia w czasie polskim: „1 lipca 2028, godz. 15:00” (data liczona w Warszawie). */
export function eventWhen(startsAt: string | null | undefined): string | null {
  if (!startsAt) return null;
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(new Date(startsAt));
  return `${formatDate(day)}, godz. ${formatTime(startsAt)}`;
}
