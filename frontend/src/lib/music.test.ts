import { describe, expect, it } from "vitest";

import { byMoment, songLabel } from "./music";

describe("muzyka", () => {
  it("opisuje utwór z wykonawcą albo bez", () => {
    expect(songLabel({ title: "Perfect", artist: "Ed Sheeran" })).toBe("Perfect — Ed Sheeran");
    expect(songLabel({ title: "Sto lat", artist: null })).toBe("Sto lat");
  });
  it("grupuje w kolejności momentów i pomija puste", () => {
    const groups = byMoment([
      { moment: "avoid" as const, title: "Disco polo" },
      { moment: "first_dance" as const, title: "Perfect" },
      { moment: "first_dance" as const, title: "Zapas" },
    ]);
    expect(groups.map((g) => [g.label, g.items.length])).toEqual([
      ["Pierwszy taniec", 2],
      ["Nie grać", 1],
    ]);
  });
});
