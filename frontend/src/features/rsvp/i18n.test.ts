import { beforeEach, describe, expect, it, vi } from "vitest";

import { dateIn, initialLang, pickLang, saveLang, STRINGS, whenIn } from "./i18n";

describe("wersja językowa strony gościa", () => {
  beforeEach(() => localStorage.clear());

  it("domyślnie wg przeglądarki, potem zapamiętany wybór gościa", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("de-DE");
    expect(initialLang()).toBe("en");
    vi.spyOn(navigator, "language", "get").mockReturnValue("pl-PL");
    expect(initialLang()).toBe("pl");
    saveLang("en");
    expect(initialLang()).toBe("en");
  });

  it("daty i liczba odpowiedzi w obu językach", () => {
    expect(dateIn("en", "2028-06-17")).toBe("17 June 2028");
    expect(dateIn("pl", "2028-06-17")).toBe("17 czerwca 2028");
    expect(whenIn("en", "2028-06-17T13:00:00Z")).toBe("17 June 2028, at 15:00");
    expect(STRINGS.en.send(2)).toBe("Send 2 replies");
    expect(STRINGS.pl.send(1)).toBe("Wyślij 1 odpowiedź");
  });

  it("oba języki mają te same klucze", () => {
    expect(Object.keys(STRINGS.en).sort()).toEqual(Object.keys(STRINGS.pl).sort());
  });
});

describe("kolejność wyboru języka", () => {
  it("wybór gościa > język zaproszenia > przeglądarka", () => {
    vi.spyOn(navigator, "language", "get").mockReturnValue("pl-PL");
    expect(pickLang(null, null)).toBe("pl");
    expect(pickLang(null, "en")).toBe("en");
    expect(pickLang("pl", "en")).toBe("pl");
  });
});
