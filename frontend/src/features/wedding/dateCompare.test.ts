import { parseDate } from "@internationalized/date";
import { describe, expect, it } from "vitest";

import { chosenDates, hhmm } from "./DateCompare";

describe("porównanie dat", () => {
  it("pomija puste i powtórzone terminy", () => {
    expect(chosenDates([parseDate("2028-06-17"), null, parseDate("2028-06-17"), parseDate("2028-03-11")])).toEqual([
      "2028-06-17",
      "2028-03-11",
    ]);
  });
  it("skraca godzinę do HH:MM", () => {
    expect(hhmm("21:12:00")).toBe("21:12");
    expect(hhmm(null)).toBeNull();
  });
});
