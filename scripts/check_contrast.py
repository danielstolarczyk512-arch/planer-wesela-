"""Kontrast par tokenów kolorów (WCAG 2.2: 1.4.3 tekst, 1.4.11 elementy interfejsu).

Sprawdza pary, które rzeczywiście występują w komponentach (nie tylko tekst na tle).
Wynik: docs/gui/kontrast.md; kod wyjścia 1, gdy jakakolwiek wymagana para nie spełnia progu.
Uruchomienie: task gui:contrast
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "design" / "tokens" / "tokens.json"
OUT = ROOT / "docs" / "gui" / "kontrast.md"

TEXT, LARGE, UI = 4.5, 3.0, 3.0
# (pierwszy plan, tło, próg, gdzie w interfejsie)
PAIRS = [
    ("textPrimary", "background", TEXT, "treść na tle aplikacji"),
    ("textPrimary", "surface", TEXT, "treść na karcie"),
    ("textPrimary", "surfaceRaised", TEXT, "treść w panelu/dialogu"),
    ("textPrimary", "accentSurface", TEXT, "treść na karcie akcentowej"),
    ("textSecondary", "background", TEXT, "tekst pomocniczy, etykiety nawigacji"),
    ("textSecondary", "surface", TEXT, "tekst pomocniczy na karcie"),
    ("textSecondary", "surfaceRaised", TEXT, "tekst pomocniczy w panelu"),
    ("textSecondary", "accentSurface", TEXT, "tekst pomocniczy na karcie akcentowej"),
    ("textSecondary", "warningBackground", TEXT, "opis w komunikacie ostrzeżenia"),
    ("textSecondary", "successBackground", TEXT, "opis w komunikacie sukcesu"),
    ("textSecondary", "errorBackground", TEXT, "opis w komunikacie błędu"),
    ("textOnPrimary", "actionPrimary", TEXT, "przycisk główny"),
    ("textOnDanger", "actionDanger", TEXT, "przycisk usuwania"),
    ("actionPrimary", "background", TEXT, "link / przycisk tekstowy na tle"),
    ("actionPrimary", "surface", TEXT, "link na karcie"),
    ("actionPrimary", "accentSurface", TEXT, "aktywna zakładka, link na karcie akcentowej"),
    ("textGold", "background", TEXT, "złoto jako tekst na tle"),
    ("textGold", "surface", TEXT, "złoto jako tekst na karcie"),
    ("goldDecorative", "background", LARGE, "złoto: tylko tekst ≥ 24 px lub ornament"),
    ("successText", "successBackground", TEXT, "status: potwierdzone"),
    ("warningText", "warningBackground", TEXT, "status: oczekuje / do uzupełnienia"),
    ("errorText", "errorBackground", TEXT, "status / komunikat błędu"),
    ("errorText", "surface", TEXT, "tekst błędu pod polem formularza"),
    ("infoText", "infoBackground", TEXT, "komunikat informacyjny"),
    ("neutralText", "neutralBackground", TEXT, "status: brak odpowiedzi / brak wyceny"),
    ("successText", "background", TEXT, "liczba potwierdzonych (duża, ale sprawdzamy jak tekst)"),
    ("warningText", "background", TEXT, "liczba oczekujących"),
    ("controlBorder", "background", UI, "obrys pola na tle aplikacji"),
    ("controlBorder", "surface", UI, "obrys pola / checkboxa na karcie"),
    ("controlBorder", "surfaceRaised", UI, "obrys pola w panelu"),
    ("controlBorder", "accentSurface", UI, "obrys chipa na tle akcentowym"),
    ("selectedBorder", "surface", UI, "obrys wybranej karty"),
    ("focusRing", "background", UI, "fokus na tle"),
    ("focusRing", "surface", UI, "fokus na karcie"),
    ("focusRing", "surfaceRaised", UI, "fokus w panelu"),
    ("focusRing", "accentSurface", UI, "fokus na karcie akcentowej"),
    ("actionPrimary", "surface", UI, "zaznaczony checkbox / radio (wypełnienie)"),
    ("textDisabled", "surface", 3.0, "nieaktywne (cel czytelności, WCAG nie wymaga)"),
]
DECORATIVE = [("separator", "surface"), ("separator", "background")]


def _lum(hex_: str) -> float:
    h = hex_.lstrip("#")[:6]
    rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def main() -> int:
    colors = json.loads(TOKENS.read_text(encoding="utf-8"))["color"]
    lines = [
        "# Kontrast tokenów (generowane: `task gui:contrast`)",
        "",
        "WCAG 2.2: tekst ≥ 4,5:1 (1.4.3), duży tekst i elementy interfejsu ≥ 3:1 (1.4.11). "
        "To kontrola tokenów, nie audyt ekranów: po implementacji obowiązuje test axe + ręczny.",
        "",
        "| Motyw | Pierwszy plan | Tło | Kontrast | Próg | Wynik | Gdzie |",
        "|---|---|---|---|---|---|---|",
    ]
    failed = 0
    for theme, palette in colors.items():
        for fg, bg, need, where in PAIRS:
            r = ratio(palette[fg]["$value"], palette[bg]["$value"])
            ok = r >= need
            failed += not ok
            mark = "✅" if ok else "❌"
            lines.append(f"| {theme} | `{fg}` | `{bg}` | {r:.2f} | {need} | {mark} | {where} |")
        for fg, bg in DECORATIVE:
            r = ratio(palette[fg]["$value"], palette[bg]["$value"])
            lines.append(
                f"| {theme} | `{fg}` | `{bg}` | {r:.2f} | — | dekoracja | "
                "nie wolno używać jako obrysu kontrolki ani jedynego wyróżnienia |"
            )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Zapisano {OUT}: {failed} par poniżej progu.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
