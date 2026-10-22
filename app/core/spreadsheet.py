"""Pliki CSV dla polskiego Excela: średnik, CRLF, UTF-8 z BOM, ochrona przed formułami."""

import csv
import io
from collections.abc import Iterable, Sequence
from decimal import Decimal

BOM = chr(0xFEFF)


def csv_safe(value: str) -> str:
    """Ochrona przed formułami w arkuszu (CSV injection): komórka zaczynająca się od = + - @."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def amount_pl(value: Decimal | None) -> str:
    """Kwota z przecinkiem dziesiętnym (polski Excel rozpozna liczbę), pusta dla braku."""
    return "" if value is None else f"{value:.2f}".replace(".", ",")


def to_csv(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return BOM + out.getvalue()
