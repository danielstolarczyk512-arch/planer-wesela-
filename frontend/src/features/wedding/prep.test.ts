import { describe, expect, it } from "vitest";

import { intOrNull, slotText } from "./PrepView";

describe("przygotowania", () => {
  it("opisuje godziny i stanowisko tylko przy kilku osobach obsługujących", () => {
    const slot = { start: "09:30", end: "10:30", artist: 2 };
    expect(slotText(slot, "fryzjerka", false)).toBe("09:30–10:30");
    expect(slotText(slot, "fryzjerka", true)).toBe("09:30–10:30 (fryzjerka 2)");
  });
  it("przyjmuje tylko liczby całkowite w zakresie", () => {
    expect(intOrNull("45", 300)).toBe(45);
    expect(intOrNull("", 300)).toBeNull();
    expect(intOrNull("2,5", 10)).toBeNull();
    expect(intOrNull("11", 10)).toBeNull();
  });
});
