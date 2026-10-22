import { describe, expect, it } from "vitest";

import { monthOptions, parseGuests } from "./WeddingWizard";

describe("kreator nowego wesela", () => {
  it("36 kolejnych miesięcy od następnego (RRRR-MM)", () => {
    const m = monthOptions(new Date(Date.UTC(2026, 10, 15))); // listopad 2026
    expect(m).toHaveLength(36);
    expect(m[0]!.id).toBe("2026-12");
    expect(m[1]!.id).toBe("2027-01");
    expect(m[0]!.label).toContain("2026");
  });

  it("liczba gości: puste = później, poza zakresem = błąd", () => {
    expect(parseGuests("")).toBeNull();
    expect(parseGuests(" 90 ")).toBe(90);
    expect(parseGuests("0")).toBe("invalid");
    expect(parseGuests("2001")).toBe("invalid");
    expect(parseGuests("dużo")).toBe("invalid");
  });
});
