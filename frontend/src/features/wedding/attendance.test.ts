import { describe, expect, it } from "vitest";

import { movedPosition, people, rangeText } from "./AttendanceView";

describe("frekwencja: teksty prognozy", () => {
  it("odmienia liczbę osób", () => {
    expect(people(1)).toBe("1 osoba");
    expect(people(3)).toBe("3 osoby");
    expect(people(5)).toBe("5 osób");
    expect(people(22)).toBe("22 osoby");
  });

  it("pokazuje zakres albo jedną liczbę", () => {
    expect(rangeText({ low: 98, high: 106 })).toBe("od 98 do 106 osób");
    expect(rangeText({ low: 4, high: 4 })).toBe("4 osoby");
  });
});

describe("lista rezerwowa: przesuwanie", () => {
  it("nie wychodzi poza listę", () => {
    expect(movedPosition(0, -1, 3)).toBeNull();
    expect(movedPosition(2, 1, 3)).toBeNull();
    expect(movedPosition(1, -1, 3)).toBe(0);
    expect(movedPosition(1, 1, 3)).toBe(2);
  });
});
