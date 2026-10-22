import { describe, expect, it } from "vitest";

import { helperProgress } from "./HelpersView";

describe("pomocnicy", () => {
  it("opisuje postęp zadań pomocnika", () => {
    expect(helperProgress(2, 1)).toBe("2 zadania do zrobienia · 1 zrobione");
    expect(helperProgress(0, 3)).toBe("3 zrobione");
    expect(helperProgress(0, 0)).toMatch(/^bez zadań/);
  });
});
