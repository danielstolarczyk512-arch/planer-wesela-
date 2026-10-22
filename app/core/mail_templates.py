# ruff: noqa: E501 — długie wiersze to style HTML w atrybutach (czytelniej w jednym wierszu).
"""Szablony e-maili: zawsze dwie części — tekst i HTML (`multipart/alternative`).

Prosty HTML ze stylami w atrybutach (klienci poczty ignorują arkusze), bez zewnętrznych obrazów,
czcionek i skryptów. Kolory z tokenów projektu (`design/tokens`). Każda wartość wstawiana do HTML
jest escapowana — nazwy wesel i imiona wpisują użytkownicy.
"""

from dataclasses import dataclass, field
from html import escape

from app.core.config import get_settings

# Tokeny projektu (jasny motyw): tło, powierzchnia, tekst, tekst drugorzędny, akcja, separator.
BACKGROUND = "#FAF7F2"
SURFACE = "#FFFFFF"
TEXT = "#242124"
TEXT_SECONDARY = "#6F656B"
ACTION = "#63364A"
ON_ACTION = "#FFFFFF"
SEPARATOR = "#E6DED5"
FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


@dataclass(frozen=True)
class Email:
    subject: str
    text: str
    html: str


@dataclass
class Section:
    title: str
    items: list[str] = field(default_factory=list)


def build(
    subject: str,
    *,
    heading: str,
    paragraphs: list[str],
    action: tuple[str, str] | None = None,
    sections: list[Section] | None = None,
    note: str | None = None,
    settings_link: bool = True,
    lang: str = "pl",
) -> Email:
    """Jedna wiadomość w dwóch wersjach. `action` = (etykieta przycisku, adres)."""
    base = get_settings().public_app_url
    settings_url = f"{base}/ustawienia"
    sections = [s for s in (sections or []) if s.items]

    text = [heading, ""]
    for p in paragraphs:
        text += [p, ""]
    if action:
        text += [f"{action[0]}: {action[1]}", ""]
    for s in sections:
        text += [f"{s.title}:", *[f"  - {item}" for item in s.items], ""]
    if note:
        text += [note, ""]
    text.append("—")
    text.append("Nasz dzień — planer wesela" if lang == "pl" else "Nasz dzień — wedding planner")
    if settings_link:
        text.append(f"Zmień powiadomienia: {settings_url}")

    h: list[str] = []
    h.append(
        f'<h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:{TEXT};">{escape(heading)}</h1>'
    )
    for p in paragraphs:
        h.append(
            f'<p style="margin:0 0 14px;font-size:16px;line-height:1.5;color:{TEXT};">{escape(p)}</p>'
        )
    if action:
        label, url = escape(action[0]), escape(action[1], quote=True)
        h.append(
            '<p style="margin:20px 0 24px;">'
            f'<a href="{url}" style="display:inline-block;padding:12px 20px;border-radius:999px;'
            f"background:{ACTION};color:{ON_ACTION};font-size:16px;font-weight:600;"
            f'text-decoration:none;">{label}</a></p>'
            f'<p style="margin:0 0 14px;font-size:13px;line-height:1.5;color:{TEXT_SECONDARY};">'
            f'{"Jeśli przycisk nie działa, skopiuj adres" if lang == "pl" else "If the button does not work, copy this address"}: <a href="{url}" style="color:{ACTION};'
            f'word-break:break-all;">{url}</a></p>'
        )
    for s in sections:
        h.append(
            f'<h2 style="margin:20px 0 8px;font-size:17px;color:{TEXT};">{escape(s.title)}</h2>'
        )
        items = "".join(
            f'<li style="margin:0 0 6px;font-size:15px;line-height:1.45;color:{TEXT};">{escape(i)}</li>'
            for i in s.items
        )
        h.append(f'<ul style="margin:0 0 8px;padding-left:20px;">{items}</ul>')
    if note:
        h.append(
            f'<p style="margin:16px 0 0;font-size:14px;line-height:1.5;color:{TEXT_SECONDARY};">'
            f"{escape(note)}</p>"
        )
    footer = "Nasz dzień — planer wesela" if lang == "pl" else "Nasz dzień — wedding planner"
    if settings_link:
        footer += (
            f' · <a href="{escape(settings_url, quote=True)}" style="color:{TEXT_SECONDARY};">'
            "Zmień powiadomienia</a>"
        )
    html = f"""<!doctype html>
<html lang="{lang if lang in ("pl", "en") else "pl"}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{escape(subject)}</title>
</head>
<body style="margin:0;padding:0;background:{BACKGROUND};font-family:{FONT};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BACKGROUND};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:{SURFACE};border:1px solid {SEPARATOR};border-radius:16px;">
<tr><td style="padding:28px 24px;">
<p style="margin:0 0 20px;font-size:14px;font-weight:600;letter-spacing:.04em;color:{ACTION};">Nasz dzień</p>
{"".join(h)}
</td></tr>
</table>
<p style="margin:16px 0 0;font-size:12px;line-height:1.5;color:{TEXT_SECONDARY};">{footer}</p>
</td></tr>
</table>
</body>
</html>
"""
    return Email(subject=subject, text="\n".join(text), html=html)
