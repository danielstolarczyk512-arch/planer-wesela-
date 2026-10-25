import { describe, expect, it } from "vitest";

import { clauseText, EXPECTED_RATES, rateOptions, WORST_RATES } from "./IndexationCard";

describe("strażnik waloryzacji", () => {
  it("opisuje klauzulę z umowy", () => {
    expect(clauseText({ indexation: "cpi", indexation_cap_percent: null })).toBe("wg inflacji GUS");
    expect(clauseText({ indexation: "cap", indexation_cap_percent: "5.00" })).toBe("z limitem 5%");
    expect(clauseText({ indexation: "none", indexation_cap_percent: null })).toBe("cena stała");
  });

  it("pokazuje zapisaną stopę, także spoza listy", () => {
    expect(rateOptions(WORST_RATES, 0.1).map((o) => o.label)).toEqual(["8%", "10%", "15%"]);
    expect(rateOptions(EXPECTED_RATES, 0.04).map((o) => o.label)).toEqual(["3%", "4%", "5%", "7%"]);
  });
});
