import { describe, expect, it } from "vitest";

import { usagePercent } from "./BudgetView";
import { normalize, statusOf } from "./GuestsView";
import { segmentOf } from "./PlanView";
import { dueLabel } from "./tasks";
import { countdown, monthsAndDays, nextPayment } from "./TodayView";
import type { Guest, Payment, Task } from "./data";

const NOW = new Date("2026-10-20T10:00:00Z");

const task = (over: Partial<Task>): Task =>
  ({ id: "t", title: "Zadanie", status: "todo", is_overdue: false, due_date: null, ...over }) as Task;

describe("Dziś: odliczanie (spec 2.4)", () => {
  it("data → liczba dni z poprawną formą", () => {
    expect(countdown({ id: "w", name: "x", wedding_date: "2028-07-01", planned_month: null, days_to_wedding: 1 })).toMatchObject({
      value: "1",
      caption: "dzień do ślubu",
    });
    expect(countdown({ id: "w", name: "x", wedding_date: "2028-07-01", planned_month: null, days_to_wedding: 22 }).caption).toBe(
      "dni do ślubu",
    );
    expect(countdown({ id: "w", name: "x", wedding_date: "2028-07-01", planned_month: null, days_to_wedding: 0 }).value).toBe("Dziś");
  });

  it("wygląd w tygodniach i miesiącach (B3)", () => {
    const w = { id: "w", name: "x", wedding_date: "2027-07-01", planned_month: null, days_to_wedding: 254 };
    expect(countdown(w, "weeks")).toMatchObject({ value: "36", caption: "tygodni i 2 dni do ślubu" });
    expect(countdown({ ...w, days_to_wedding: 14 }, "weeks").caption).toBe("tygodnie do ślubu");
    expect(countdown({ ...w, days_to_wedding: 5 }, "weeks")).toMatchObject({ value: "5", caption: "dni do ślubu" });
    // 20.10.2026 → 1.07.2027: 8 pełnych miesięcy (do 20.06) i 11 dni.
    expect(countdown(w, "months", NOW)).toMatchObject({ value: "8", caption: "miesięcy i 11 dni do ślubu" });
    expect(countdown({ ...w, wedding_date: "2026-11-20", days_to_wedding: 31 }, "months", NOW).caption).toBe("miesiąc do ślubu");
  });

  it("pełne miesiące: koniec miesiąca i mniej niż miesiąc", () => {
    expect(monthsAndDays("2027-03-01", new Date("2027-01-31T10:00:00Z"))).toEqual({ months: 1, days: 1 });
    expect(monthsAndDays("2026-11-05", NOW)).toEqual({ months: 0, days: 16 });
  });

  it("tylko miesiąc → przybliżenie w miesiącach, nie fałszywe dni", () => {
    const c = countdown({ id: "w", name: "x", wedding_date: null, planned_month: "2027-08", days_to_wedding: 285 });
    expect(c.value).toBe("ok. 9");
    expect(c.caption).toBe("miesięcy do ślubu");
    expect(c.overline).toBe("sierpień 2027");
  });

  it("najbliższa płatność: najpierw zaległe, opłacone pomijane", () => {
    const pays = [
      { id: "a", status: "scheduled", is_overdue: false, due_date: "2026-11-01" },
      { id: "b", status: "paid", is_overdue: false, due_date: "2026-10-21" },
      { id: "c", status: "scheduled", is_overdue: true, due_date: "2026-10-01" },
    ] as Payment[];
    expect(nextPayment(pays)?.id).toBe("c");
    expect(nextPayment([])).toBeNull();
  });
});

describe("Plan", () => {
  it("segmenty: po terminie i 30 dni → Teraz; dalej i bez terminu → Później; zrobione osobno", () => {
    expect(segmentOf(task({ is_overdue: true, due_date: "2026-09-01" }), NOW)).toBe("teraz");
    expect(segmentOf(task({ due_date: "2026-11-15" }), NOW)).toBe("teraz");
    expect(segmentOf(task({ due_date: "2027-03-01" }), NOW)).toBe("pozniej");
    expect(segmentOf(task({ due_date: null }), NOW)).toBe("pozniej");
    expect(segmentOf(task({ status: "done" }), NOW)).toBe("zrobione");
  });

  it("termin: bez roku w bieżącym roku, z rokiem w innym, informacja o upływie", () => {
    expect(dueLabel(task({ due_date: "2026-12-10" }), NOW)).toBe("Do 10 grudnia");
    expect(dueLabel(task({ due_date: "2027-01-15" }), NOW)).toBe("Do 15 stycznia 2027");
    expect(dueLabel(task({ due_date: "2026-02-07" }), NOW)).toBe("Termin minął: 7 lutego");
    expect(dueLabel(task({ due_date: null }), NOW)).toBe("Bez terminu");
  });
});

describe("Budżet", () => {
  it("procent wykorzystania limitu", () => {
    expect(usagePercent("51500.00", "65000.00")).toBe(79);
    expect(usagePercent("70000.00", "65000.00")).toBe(108);
    expect(usagePercent("100.00", "0.00")).toBe(0);
  });
});

describe("Goście", () => {
  it("wyszukiwanie bez polskich znaków i wielkości liter", () => {
    expect(normalize("Zielińska")).toBe(normalize("zielinska"));
    expect(normalize("ŁUKASZ Żółć")).toBe("lukasz zolc");
  });

  it("brak wpisu obecności = brak odpowiedzi (nie odmowa)", () => {
    const g = { attendance: { e1: "declined" } } as unknown as Guest;
    expect(statusOf(g, "e1")).toBe("declined");
    expect(statusOf(g, "e2")).toBe("pending");
    expect(statusOf(g, undefined)).toBe("pending");
  });
});
