import { describe, expect, it } from "vitest";

import { diffText } from "./ScenarioCompare";

const pln = (amount: string) => ({ amount, currency: "PLN" as const });

describe("„co jeśli”: różnice opisane słowami", () => {
  it("dodatnia, ujemna i zerowa różnica", () => {
    expect(diffText(pln("3000.00"), "w dopłacie").replace(/\s/g, " ")).toBe("+3 000 zł w dopłacie");
    expect(diffText(pln("-1250.50")).replace(/\s/g, " ")).toBe("−1 250,50 zł");
    expect(diffText(pln("0.00"), "w dopłacie")).toBe("bez zmian w dopłacie");
  });
});
