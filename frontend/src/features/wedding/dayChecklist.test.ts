import { describe, expect, it } from "vitest";

import { progress } from "./DayChecklist";

describe("co zabrać", () => {
  it("liczy postęp listy", () => {
    expect(progress([{ done: true }, { done: false }, { done: true }])).toBe("2 z 3");
    expect(progress([])).toBe("0 z 0");
  });
});
