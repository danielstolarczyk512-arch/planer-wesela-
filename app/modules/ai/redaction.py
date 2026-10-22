"""Redakcja danych osobowych przed wysłaniem tekstu do dostawcy ZEWNĘTRZNEGO.

Lokalny model (Ollama) dostaje tekst bez zmian: dane nie opuszczają serwera.
Redagujemy: PESEL (z sumą kontrolną), numery rachunków (IBAN PL / 26 cyfr), e-maile, telefony.
Ceny i kwoty pozostają: są potrzebne do analizy oferty.
"""

import re

_PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
_PESEL = re.compile(r"(?<!\d)\d{11}(?!\d)")
_ACCOUNT = re.compile(r"(?<![\dA-Z])(?:PL\s?)?\d{2}(?:[ -]?\d{4}){6}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+48[ -]?)?(?:\d{3}[ -]?\d{3}[ -]?\d{3})(?!\d)")


def _pesel_valid(digits: str) -> bool:
    check = sum(int(d) * w for d, w in zip(digits[:10], _PESEL_WEIGHTS, strict=True)) % 10
    return (10 - check) % 10 == int(digits[10])


def redact(text: str) -> tuple[str, dict[str, int]]:
    counts = {"pesel": 0, "account": 0, "email": 0, "phone": 0}

    def sub(pattern: re.Pattern[str], label: str, token: str, predicate: object = None) -> None:
        nonlocal text

        def repl(m: re.Match[str]) -> str:
            if callable(predicate) and not predicate(m.group(0)):
                return m.group(0)
            counts[label] += 1
            return token

        text = pattern.sub(repl, text)

    sub(_ACCOUNT, "account", "[RACHUNEK]")
    sub(_PESEL, "pesel", "[PESEL]", _pesel_valid)
    sub(_EMAIL, "email", "[EMAIL]")
    sub(_PHONE, "phone", "[TELEFON]")
    return text, counts
