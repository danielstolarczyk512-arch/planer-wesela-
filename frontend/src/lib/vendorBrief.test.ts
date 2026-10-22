import { describe, expect, it } from "vitest";

import { briefLabels, linesToList, linesToPeople, peopleToLines } from "./vendorBrief";

const NL = String.fromCharCode(10);

describe("informacje dla usługodawcy", () => {
  it("nazywa sekcje wg rodzaju usługodawcy", () => {
    expect(briefLabels("band").avoid).toBe("Nie grać");
    expect(briefLabels("photographer").must).toBe("Ujęcia obowiązkowe");
    expect(briefLabels("florist").must).toBe("Koniecznie");
  });

  it("zamienia wiersze na listę bez pustych pozycji", () => {
    expect(linesToList(`  Perfect ${NL}${NL}Wejście: Marsz`)).toEqual(["Perfect", "Wejście: Marsz"]);
  });

  it("czyta osoby z rolą po myślniku i wraca do tekstu", () => {
    const people = linesToPeople(`Babcia Halina — mama Pana Młodego${NL}Wujek Staś - świadek${NL}Ola`);
    expect(people).toEqual([
      { name: "Babcia Halina", role: "mama Pana Młodego" },
      { name: "Wujek Staś", role: "świadek" },
      { name: "Ola", role: "gość" },
    ]);
    expect(peopleToLines(people.slice(0, 1))).toBe("Babcia Halina — mama Pana Młodego");
  });
});
