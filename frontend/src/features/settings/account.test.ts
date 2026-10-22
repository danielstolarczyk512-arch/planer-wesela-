import { describe, expect, it } from "vitest";

import { deviceName } from "./AccountSection";

describe("nazwa urządzenia z User-Agent", () => {
  it("rozpoznaje popularne przeglądarki i systemy", () => {
    expect(deviceName("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0 Safari/537.36")).toBe("Chrome · Windows");
    expect(deviceName("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1")).toBe(
      "Safari · iPhone / iPad",
    );
    expect(deviceName("Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/141.0 Mobile Safari/537.36 EdgA/141.0 Edg/141.0")).toBe("Edge · Android");
    expect(deviceName(null)).toBe("Nieznane urządzenie");
  });
});
