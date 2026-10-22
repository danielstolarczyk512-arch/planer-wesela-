import { describe, expect, it } from "vitest";

import { clauseText } from "./IndexationCard";

describe("strażnik waloryzacji", () => {
  it("opisuje klauzulę z umowy", () => {
    expect(clauseText({ indexation: "cpi", indexation_cap_percent: null })).toBe("wg inflacji GUS");
    expect(clauseText({ indexation: "cap", indexation_cap_percent: "5.00" })).toBe("z limitem 5%");
    expect(clauseText({ indexation: "none", indexation_cap_percent: null })).toBe("cena stała");
  });
});
