"""Kody QR jako SVG do użycia w `<img src="data:image/svg+xml…">` (RSVP, MFA)."""

import io

import segno


def qr_svg(text: str, *, scale: int) -> str:
    """Czarny kod na białym tle, bez stylów inline (CSP).

    Przestrzeń nazw `xmlns` jest wymagana: bez niej przeglądarka nie wyrenderuje SVG wstawionego
    jako obraz (data URI) — `svg_inline` ją pomija, bo jest przeznaczony do HTML.
    """
    buff = io.BytesIO()
    segno.make(text, error="m").save(
        buff,
        kind="svg",
        xmldecl=False,
        svgns=True,
        nl=False,
        scale=scale,
        border=2,
        dark="#000",
        light="#fff",
    )
    return buff.getvalue().decode("utf-8")
