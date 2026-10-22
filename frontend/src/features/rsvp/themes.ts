/**
 * Wygląd strony dla gości (Premium): motyw i kolor akcentu. Bez zewnętrznych czcionek i obrazów (CSP).
 * Kolory akcentu służą do tekstu (nagłówki, linki), więc każdy ma wersję jasną i ciemną
 * sprawdzoną pod kontrast WCAG AA (≥ 4,5 : 1) — test w styles/tokens.test.ts.
 */
import type { CSSProperties } from "react";

import type { components } from "../../api/schema";

export type GuestTheme = components["schemas"]["RsvpTheme"]["style"];
export type Accent = NonNullable<components["schemas"]["RsvpTheme"]["accent"]>;

export const THEMES: { value: GuestTheme; label: string }[] = [
  { value: "classic", label: "Klasyczny" },
  { value: "garden", label: "Ogród" },
  { value: "modern", label: "Nowoczesny" },
];

export const ACCENTS: { id: Accent; label: string; light: string; dark: string }[] = [
  { id: "rose", label: "Róż", light: "#A3324F", dark: "#F2A7B8" },
  { id: "sage", label: "Szałwia", light: "#3F6B4E", dark: "#A8CFA9" },
  { id: "navy", label: "Granat", light: "#2B4A7E", dark: "#A9C1EC" },
  { id: "gold", label: "Złoto", light: "#7A5A12", dark: "#E3C27A" },
  { id: "plum", label: "Śliwka", light: "#6B3A6E", dark: "#D9AEDB" },
  { id: "teal", label: "Morski", light: "#1F6566", dark: "#8FD3D1" },
];

/** Zmienne CSS akcentu dla kontenera strony (rsvp.css wybiera jasną albo ciemną). */
export function accentStyle(accent: Accent | null | undefined): CSSProperties | undefined {
  const a = ACCENTS.find((x) => x.id === accent);
  if (!a) return undefined;
  return { "--guest-accent-light": a.light, "--guest-accent-dark": a.dark } as CSSProperties;
}

/** Kontrast WCAG 2.x między dwoma kolorami #RRGGBB. */
export function contrast(a: string, b: string): number {
  const lum = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r! + 0.7152 * g! + 0.0722 * bl!;
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}
