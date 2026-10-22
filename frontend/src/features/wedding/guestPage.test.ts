import { describe, expect, it } from "vitest";

import { sentAt } from "./GuestPageView";

describe("strona gościa", () => {
  it("podaje czas wysyłki komunikatu w czasie polskim", () => {
    expect(sentAt("2026-10-22T12:05:00Z")).toBe("22 października 14:05");
  });
});
