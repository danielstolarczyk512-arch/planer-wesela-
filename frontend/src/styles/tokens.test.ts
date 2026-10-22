import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { ACCENTS, contrast } from "../features/rsvp/themes";

/** tokens.css musi być aktualny względem design/tokens/tokens.json (task gui:tokens). */
describe("tokeny", () => {
  const root = resolve(__dirname, "../../..");
  const tokens = JSON.parse(readFileSync(resolve(root, "design/tokens/tokens.json"), "utf8")) as {
    color: Record<string, Record<string, { $value: string }>>;
  };
  const css = readFileSync(resolve(__dirname, "tokens.css"), "utf8");
  const kebab = (s: string) => s.replace(/(?<!^)(?=[A-Z])/g, "-").toLowerCase();

  it.each(Object.entries(tokens.color))("motyw %s: każdy kolor jest w tokens.css z aktualną wartością", (_, palette) => {
    for (const [name, token] of Object.entries(palette)) {
      expect(css).toContain(`--wp-${kebab(name)}: ${token.$value};`);
    }
  });

  it("tryb ograniczonego ruchu zeruje przesunięcia i skalę", () => {
    expect(css).toMatch(/\.reduce-motion \{[^}]*--wp-motion-detail-translate: 0px;[^}]*--wp-motion-press-scale: 1;/s);
  });
});

describe("strona dla gości: kolory akcentu", () => {
  const css = readFileSync(resolve(__dirname, "tokens.css"), "utf8");
  const value = (name: string, from: number) => css.slice(from).match(new RegExp(`--wp-${name}: (#[0-9A-Fa-f]{6});`))![1]!;
  const light = { surface: value("surface", 0), background: value("background", 0) };
  const darkAt = css.indexOf(":root[data-theme=\"dark\"]");
  const dark = { surface: value("surface", darkAt), background: value("background", darkAt) };

  it.each(ACCENTS)("$label: kontrast tekstu ≥ 4,5 : 1 w jasnym i ciemnym motywie", (a) => {
    for (const bg of [light.surface, light.background]) expect(contrast(a.light, bg)).toBeGreaterThanOrEqual(4.5);
    for (const bg of [dark.surface, dark.background]) expect(contrast(a.dark, bg)).toBeGreaterThanOrEqual(4.5);
  });
});
