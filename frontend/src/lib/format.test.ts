import { describe, expect, it } from "vitest";

import { daysUntil, formatDate, formatMoney, parseAmountInput, plural, todayInWarsaw } from "./format";

const NBSP = String.fromCharCode(0xa0);
const pln = (amount: string) => ({ amount, currency: "PLN" });

describe("formatMoney", () => {
  it("grupuje także liczby czterocyfrowe i nie łamie kwoty z walutą", () => {
    expect(formatMoney(pln("5000.00"))).toBe(`5${NBSP}000${NBSP}zł`);
    expect(formatMoney(pln("37200.00"))).toBe(`37${NBSP}200${NBSP}zł`);
  });

  it("pokazuje grosze tylko, gdy są", () => {
    expect(formatMoney(pln("1250000.50"))).toBe(`1${NBSP}250${NBSP}000,50${NBSP}zł`);
    expect(formatMoney(pln("1500.00"), { cents: true })).toBe(`1${NBSP}500,00${NBSP}zł`);
  });

  it("brak kwoty to „Brak wyceny”, nigdy 0 zł", () => {
    expect(formatMoney(null)).toBe("Brak wyceny");
    expect(formatMoney(undefined)).toBe("Brak wyceny");
  });

  it("odrzuca nieprawidłowy napis zamiast pokazać błędną kwotę", () => {
    expect(() => formatMoney(pln("12,5"))).toThrow();
  });
});

describe("parseAmountInput", () => {
  it.each([
    ["1500", "1500.00"],
    ["1500,5", "1500.50"],
    ["1 500,50", "1500.50"],
    [`1${NBSP}500,50 zł`, "1500.50"],
    ["0007", "7.00"],
  ])("%s → %s", (raw, expected) => {
    expect(parseAmountInput(raw)).toBe(expected);
  });

  it.each(["", "abc", "1,234", "-5", "1.5.5"])("odrzuca %s", (raw) => {
    expect(parseAmountInput(raw)).toBeNull();
  });
});

describe("plural", () => {
  const left = { one: "Zostało # zadanie", few: "Zostały # zadania", many: "Zostało # zadań", other: "Zostało # zadania" };
  it.each([
    [1, "Zostało 1 zadanie"],
    [3, "Zostały 3 zadania"],
    [5, "Zostało 5 zadań"],
    [12, "Zostało 12 zadań"],
    [22, "Zostały 22 zadania"],
  ])("%i", (n, expected) => {
    expect(plural(n, left)).toBe(expected);
  });
});

describe("daty w strefie Europe/Warsaw", () => {
  it("formatuje datę kalendarzową po polsku", () => {
    expect(formatDate("2028-07-01")).toBe("1 lipca 2028");
  });

  it("dzień liczony wg Warszawy, nie wg UTC", () => {
    // 23:30 UTC 30 czerwca = 01:30 1 lipca w Warszawie (czas letni).
    expect(todayInWarsaw(new Date("2028-06-30T23:30:00Z"))).toBe("2028-07-01");
    expect(daysUntil("2028-07-01", new Date("2028-06-30T23:30:00Z"))).toBe(0);
  });

  it("zmiana czasu nie psuje liczby dni", () => {
    // Między 1 marca a 1 kwietnia jest zmiana czasu (dzień ma 23 h): nadal 31 dni.
    expect(daysUntil("2028-04-01", new Date("2028-03-01T10:00:00Z"))).toBe(31);
  });
});
