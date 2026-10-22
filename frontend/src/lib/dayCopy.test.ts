import { beforeEach, describe, expect, it } from "vitest";

import { clearDayCopies, isExpired, listWeddingCopies, publicCopyKey, readDayCopy, saveDayCopy, weddingCopyKey } from "./dayCopy";

const item = {
  id: "1",
  title: "Pierwszy taniec",
  starts_at: "2028-07-01T21:00:00+02:00",
  ends_at: "2028-07-01T21:10:00+02:00",
  location: "Sala",
  plan_b: null,
  preparations: "Muzyka",
  vendor_name: "DJ",
};

describe("kopia programu dnia na urządzeniu", () => {
  beforeEach(() => localStorage.clear());

  it("zapisuje tylko pola programu i odczytuje do dnia po ślubie", () => {
    const key = weddingCopyKey("w1");
    // Dodatkowe pole (np. dane gości) nie trafia do pamięci przeglądarki.
    saveDayCopy(key, { name: "Wesele", wedding_date: "2028-07-01", items: [{ ...item, guests: ["Ania"] } as typeof item] }, new Date("2028-06-30T10:00:00Z"));
    expect(localStorage.getItem("wp-day-copy:w:w1")).not.toContain("Ania");
    expect(readDayCopy(key, "2028-07-01")?.items[0]?.title).toBe("Pierwszy taniec");
    expect(readDayCopy(key, "2028-07-02")).not.toBeNull();
    expect(readDayCopy(key, "2028-07-03")).toBeNull();
    expect(localStorage.getItem("wp-day-copy:w:w1")).toBeNull(); // wygasła — usunięta
  });

  it("bez daty ślubu kopia żyje tydzień od zapisu", () => {
    const copy = { name: "X", wedding_date: null, saved_at: "2028-07-01T08:00:00Z", items: [] };
    expect(isExpired(copy, "2028-07-08")).toBe(false);
    expect(isExpired(copy, "2028-07-09")).toBe(true);
  });

  it("lista kopii z kont pomija stronę usługodawcy; wylogowanie czyści wszystko", () => {
    saveDayCopy(weddingCopyKey("w1"), { name: "A", wedding_date: "2028-07-01", items: [item] });
    saveDayCopy(publicCopyKey("abcdefghijklmnopqrstuvwxyz"), { name: "B", wedding_date: "2028-07-01", items: [item] });
    expect(listWeddingCopies("2028-07-01").map((c) => c.name)).toEqual(["A"]);
    localStorage.setItem("inne", "zostaje");
    clearDayCopies();
    expect(listWeddingCopies("2028-07-01")).toEqual([]);
    expect(readDayCopy(publicCopyKey("abcdefghijklmnopqrstuvwxyz"), "2028-07-01")).toBeNull();
    expect(localStorage.getItem("inne")).toBe("zostaje");
  });
});
