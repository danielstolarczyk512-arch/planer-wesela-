import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { CSP } from "../../vite.config";

describe("CSP", () => {
  it("Caddy (produkcja) i vite preview (testy E2E) mają tę samą politykę", () => {
    const caddy = readFileSync(resolve(__dirname, "../../../deploy/Caddyfile"), "utf8");
    expect(caddy).toContain(`Content-Security-Policy "${CSP}"`);
  });

  it("bez skryptów inline i bez unsafe-inline dla bloków stylu", () => {
    expect(CSP).toContain("script-src 'self';");
    expect(CSP).not.toMatch(/(script-src|style-src) [^;]*'unsafe-inline'/);
  });
});
