import { describe, expect, it } from "vitest";

import { docState } from "./CeremonyDocsView";
import { activeTab } from "./WeddingShell";

describe("dokumenty do ślubu", () => {
  it("opisuje stan dokumentu", () => {
    expect(docState({ status: "too_early", earliest: "2028-01-01", latest: null, expires_on: null }).label).toBe("Najwcześniej od 1 stycznia 2028");
    expect(docState({ status: "expires", earliest: null, latest: null, expires_on: "2028-02-20" }).tone).toBe("error");
    expect(docState({ status: "ok", earliest: null, latest: null, expires_on: "2028-08-01" }).label).toBe("Ważny do 1 sierpnia 2028");
    expect(docState({ status: "no_date", earliest: null, latest: null, expires_on: null }).label).toBe("Ustawcie datę ślubu");
  });

  it("strona dokumentów należy do zakładki Plan", () => {
    expect(activeTab("formalnosci")).toBe("plan");
  });
});
