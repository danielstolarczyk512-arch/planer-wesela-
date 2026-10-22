"""Tokeny GUI (design/tokens/*.json) → zmienne CSS (--wp-*) dla aplikacji i podglądu.

Jedno źródło prawdy dla kolorów, fontów, typografii, promieni i ruchu. Wynik trafia do
frontend/src/styles/tokens.css i design/podglad/tokens.css (pliki w repozytorium;
test frontendu sprawdza, że są aktualne). Zamiast Style Dictionary: ten skrypt,
bo tokeny mają motywy i wartości złożone, a zależność byłaby większa niż generator.
Tekst w rem z interlinią bez jednostki: powiększenie tekstu w systemie skaluje wszystko.
Uruchomienie: task gui:tokens
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "design" / "tokens"
OUTPUTS = [
    ROOT / "frontend" / "src" / "styles" / "tokens.css",
    ROOT / "design" / "podglad" / "tokens.css",
]


def rem(px: float) -> str:
    return f"{px / 16:g}rem"


def kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def theme_block(selector: str, theme: str, t: dict, m: dict) -> list[str]:
    lines = [f"{selector} {{", f"  color-scheme: {theme};"]
    for name, token in t["color"][theme].items():
        lines.append(f"  --wp-{kebab(name)}: {token['$value']};")
    for role, token in t["font"][theme].items():
        families = ", ".join(f'"{f}"' if " " in f else f for f in token["$value"])
        lines.append(f"  --wp-font-{role}: {families};")
    lines.append(f"  --wp-radius-card: {t['radius']['card'][theme]}px;")
    lines.append(f"  --wp-radius-button: {t['radius']['button'][theme]}px;")
    lines.append(f"  --wp-shadow-card: {_shadow(t['elevation'][theme]['card'])};")
    lines.append(f"  --wp-shadow-sheet: {_shadow(t['elevation'][theme]['sheet'])};")
    lines.append("}")
    return lines


def _shadow(value: str) -> str:
    return "none" if value.startswith("none") else value


def main() -> None:
    t = json.loads((TOKENS / "tokens.json").read_text(encoding="utf-8"))
    m = json.loads((TOKENS / "motion.json").read_text(encoding="utf-8"))
    out = [
        "/* Wygenerowane z design/tokens/*.json przez scripts/tokens_to_css.py — nie edytować. */"
    ]
    out += [":root {"]
    for i, v in enumerate(t["space"]["$value"], start=1):
        out.append(f"  --wp-space-{i}: {v}px;")
    for name, v in t["typography"].items():
        val = v["$value"]
        if "size" in val:
            line_height = round(val["lineHeight"] / val["size"], 4)
            out.append(f"  --wp-type-{kebab(name)}: {rem(val['size'])}/{line_height:g};")
            out.append(f"  --wp-type-{kebab(name)}-size: {rem(val['size'])};")
        else:
            out.append(f"  --wp-type-{kebab(name)}-min: {rem(val['min'])};")
            out.append(f"  --wp-type-{kebab(name)}-max: {rem(val['max'])};")
    lay = t["layout"]
    out += [
        f"  --wp-pad: {lay['phonePadding']}px;",
        f"  --wp-pad-small: {lay['smallPhonePadding']}px;",
        f"  --wp-content-max: {lay['contentMaxWidth']}px;",
        f"  --wp-touch: {lay['touchTargetMinimum']}px;",
        f"  --wp-focus-width: {lay['focusRingWidth']}px;",
        f"  --wp-focus-offset: {lay['focusRingOffset']}px;",
        f"  --wp-radius-sheet: {t['radius']['sheetTop']}px;",
    ]
    for name, curve in m["easing"].items():
        out.append(f"  --wp-ease-{name}: cubic-bezier({', '.join(str(c) for c in curve)});")
    durations: list[tuple[str, int]] = []
    for name, tr in m["transitions"].items():
        for key, val in tr.items():
            if "uration" in key or key == "delayPerItem":
                var = f"--wp-motion-{kebab(name)}-{kebab(key)}"
                durations.append((var, val))
                out.append(f"  {var}: {val}ms;")
    tr = m["transitions"]
    out += [
        f"  --wp-motion-detail-translate: {tr['detail']['translateX']}px;",
        f"  --wp-motion-press-scale: {tr['press']['scaleTo']};",
        f"  --wp-motion-dialog-scale: {tr['dialog']['scaleFrom']};",
        "  --wp-motion-sheet-translate: 100%;",
        "}",
    ]
    out += theme_block(':root, :root[data-theme="light"]', "light", t, m)
    out += [
        "@media (prefers-color-scheme: dark) {",
        *("  " + line for line in theme_block(':root:not([data-theme="light"])', "dark", t, m)),
        "}",
    ]
    out += theme_block(':root[data-theme="dark"]', "dark", t, m)
    cap = m["reducedMotion"]["opacityMaxDuration"]
    reduced = [
        "  --wp-reduce: 1;",
        "  --wp-motion-detail-translate: 0px;",
        "  --wp-motion-press-scale: 1;",
        "  --wp-motion-dialog-scale: 1;",
        "  --wp-motion-sheet-translate: 0px;",
        *(f"  {var}: {min(val, cap)}ms;" for var, val in durations if var.endswith("duration")),
        "  --wp-motion-stagger-delay-per-item: 0ms;",
    ]
    out += [
        "/* Ograniczenie ruchu (system albo ustawienie aplikacji): bez przesunięć i skalowania,",
        f"   wyłącznie przenikania do {cap} ms. Komponenty używają tych zmiennych. */",
        "@media (prefers-reduced-motion: reduce) {",
        "  :root {",
        *("  " + line for line in reduced),
        "  }",
        "}",
        ":root.reduce-motion {",
        *reduced,
        "}",
    ]
    for path in OUTPUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"Zapisano {path}")


if __name__ == "__main__":
    main()
