import { describe, expect, it } from "vitest";

import { coveredPercent, settleText } from "./FundersView";
import { activeTab } from "./WeddingShell";

const pln = (amount: string) => ({ amount, currency: "PLN" as const });

describe("portfel sponsorów", () => {
  it("opisuje stan obietnicy", () => {
    expect(settleText({ pledged_amount: null, to_settle: null }).text).toBe("Bez ustalonej kwoty");
    expect(settleText({ pledged_amount: pln("20000.00"), to_settle: pln("0.00") }).tone).toBe("success");
    expect(settleText({ pledged_amount: pln("20000.00"), to_settle: pln("4000.00") }).text).toMatch(/^Do rozpisania/);
    expect(settleText({ pledged_amount: pln("20000.00"), to_settle: pln("-1500.00") }).tone).toBe("warning");
  });

  it("liczy, ile obiecanej kwoty dotarło (max 100%)", () => {
    expect(coveredPercent({ pledged_amount: pln("20000.00"), covered: pln("5000.00") })).toBe(25);
    expect(coveredPercent({ pledged_amount: pln("1000.00"), covered: pln("3000.00") })).toBe(100);
    expect(coveredPercent({ pledged_amount: null, covered: pln("100.00") })).toBeNull();
  });

  it("strony portfela i wkładu mają swoje zakładki", () => {
    expect(activeTab("sponsorzy")).toBe("budzet");
    expect(activeTab("wklad")).toBe("wklad");
  });
});
