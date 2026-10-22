import { describe, expect, it } from "vitest";

import { decodeCsv, normalizeHeaders } from "./GuestImport";

describe("import gości: przygotowanie pliku", () => {
  it("polskie nagłówki → kolumny API (bez względu na znaki i wielkość liter)", () => {
    expect(normalizeHeaders("Zaproszenie;Imię;NAZWISKO;Dieta;E-mail\r\nKowalscy;Anna;Kowalska;;a@b.pl")).toBe(
      "household;first_name;last_name;dietary;email\r\nKowalscy;Anna;Kowalska;;a@b.pl",
    );
    expect(normalizeHeaders("rodzina,imie,telefon\nNowak,Ewa,600")).toBe("household,first_name,phone\nNowak,Ewa,600");
  });

  it("Windows-1250 z Excela: polskie znaki odczytane poprawnie", () => {
    // „Imię;Łódź” w Windows-1250: ę = 0xEA, Ł = 0xA3, ó = 0xF3, ź = 0x9F
    const bytes = new Uint8Array([0x49, 0x6d, 0x69, 0xea, 0x3b, 0xa3, 0xf3, 0x64, 0x9f]);
    expect(decodeCsv(bytes.buffer)).toBe("Imię;Łódź");
  });

  it("UTF-8 zostaje UTF-8", () => {
    expect(decodeCsv(new TextEncoder().encode("Imię;Łódź").buffer as ArrayBuffer)).toBe("Imię;Łódź");
  });
});
