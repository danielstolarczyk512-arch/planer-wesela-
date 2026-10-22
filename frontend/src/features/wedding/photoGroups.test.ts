import { describe, expect, it } from "vitest";

import { duration } from "./PhotoGroupsView";

describe("zdjęcia grupowe", () => {
  it("podaje czas w minutach albo godzinach", () => {
    expect(duration(35)).toBe("ok. 35 min");
    expect(duration(60)).toBe("ok. 1 h");
    expect(duration(65)).toBe("ok. 1 h 5 min");
  });
});
