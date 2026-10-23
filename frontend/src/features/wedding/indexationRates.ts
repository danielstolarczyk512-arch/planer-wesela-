/**
 * Domyślne założenia podwyżek cen z umów: wspólne dla karty w Budżecie i podpowiedzi na Dziś,
 * żeby oba ekrany liczyły ten sam wariant (audyt 2026-10-23, 4.4).
 */
export const EXPECTED_RATE = "0.05";
export const WORST_RATE = "0.10";

/** „10%” z „0.10”. */
export const percent = (rate: string) => `${Math.round(Number(rate) * 100)}%`;
