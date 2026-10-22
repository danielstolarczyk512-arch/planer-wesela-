import { describe, expect, it } from "vitest";

import { monthRange } from "./CalendarView";
import { drinksNeeded } from "./DrinksCalculator";
import { filled } from "./OfferEditor";
import { subtaskProgress, topLevel } from "./tasks";
import { activeTab } from "./WeddingShell";
import type { Task } from "./data";

const task = (over: Partial<Task>): Task => ({ id: "t", title: "Zadanie", status: "todo", parent_task_id: null, ...over }) as Task;

describe("nawigacja: aktywna zakładka działu", () => {
  it("podstrony działu podświetlają zakładkę", () => {
    expect(activeTab("")).toBe("");
    expect(activeTab("uslugodawcy/123")).toBe("budzet");
    expect(activeTab("oferty/porownanie")).toBe("budzet");
    expect(activeTab("stoly")).toBe("goscie");
    expect(activeTab("podglad-goscia")).toBe("goscie");
    expect(activeTab("frekwencja")).toBe("goscie");
    expect(activeTab("kalendarz")).toBe("plan");
    expect(activeTab("druk/stoly")).toBe("wiecej");
    expect(activeTab("dzien")).toBe("dzien");
  });
});

describe("plan: podzadania (lista dokumentów)", () => {
  const all = [
    task({ id: "p" }),
    task({ id: "a", parent_task_id: "p", status: "done" }),
    task({ id: "b", parent_task_id: "p" }),
    task({ id: "c", parent_task_id: "p", status: "skipped" }),
  ];
  it("lista pokazuje tylko zadania nadrzędne", () => {
    expect(topLevel(all).map((t) => t.id)).toEqual(["p"]);
  });
  it("postęp liczy podzadania bez pominiętych", () => {
    expect(subtaskProgress(all, "p")).toEqual({ done: 1, total: 2 });
    expect(subtaskProgress(all, "a")).toBeUndefined();
  });
});

describe("kalendarz: zakres miesiąca", () => {
  it("luty w roku przestępnym i przejście roku", () => {
    expect(monthRange("2028-02")).toEqual({ start: "2028-02-01", end: "2028-02-29", prev: "2028-01", next: "2028-03" });
    expect(monthRange("2026-12").next).toBe("2027-01");
    expect(monthRange("2027-01").prev).toBe("2026-12");
  });
});

describe("oferta z szablonu: puste podpowiedzi pomijane", () => {
  it("zostają pozycje z kwotą, „w cenie” i dodane ręcznie", () => {
    const rows = [
      { key: "1", label: "Menu", kind: "per_guest", amount: "300", quantity: "", included: false, optional: false, template: true },
      { key: "2", label: "Tort", kind: "fixed", amount: null, quantity: "", included: false, optional: false, template: true },
      { key: "3", label: "Napoje", kind: "per_guest", amount: null, quantity: "", included: true, optional: false, template: true },
      { key: "4", label: "", kind: "fixed", amount: null, quantity: "", included: false, optional: false },
    ] as Parameters<typeof filled>[0];
    expect(filled(rows).map((r) => r.key)).toEqual(["1", "3", "4"]);
  });
});

describe("kalkulator alkoholu", () => {
  it("liczy butelki w górę od liczby pijących gości", () => {
    expect(drinksNeeded({ adults: 100, allGuests: 110, drinkingShare: 80, vodkaPerDrinker: 0.5, winePerDrinker: 0.33, softPerGuest: 1.5 })).toEqual({
      vodka: 80,
      wine: 27,
      soft: 165,
    });
    expect(drinksNeeded({ adults: 0, allGuests: 0, drinkingShare: 80, vodkaPerDrinker: 0.5, winePerDrinker: 0.33, softPerGuest: 1.5 })).toEqual({
      vodka: 0,
      wine: 0,
      soft: 0,
    });
  });
});
