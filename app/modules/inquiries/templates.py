# ruff: noqa: E501, RUF001
"""Szkic zapytania do firmy: stała, sprawdzona treść bez ujawniania budżetu pary."""

import hashlib
import re
from decimal import Decimal

from app.modules.concierge.matching import WeddingContext
from app.modules.vendors.models import CATEGORIES

DEFAULT_QUESTIONS = (
    "Czy w tym terminie macie Państwo wolną datę?",
    "Jaki zakres usługi obejmuje oferta i jaka jest PEŁNA cena (wraz z dopłatami)?",
    "Czy cena zawiera dojazd? Jeśli nie — jaki jest koszt dojazdu do miejscowości wesela?",
    "Ile godzin obejmuje usługa i jak rozliczane są nadgodziny?",
    "Jakie są warunki płatności (zadatek, terminy rat) i do kiedy ważna jest oferta?",
)


def content_hash(to_email: str, subject: str, body: str) -> str:
    """Odcisk treści, której dotyczy zgoda: adresat + temat + treść."""
    raw = "\x1f".join((to_email.strip().lower(), subject.strip(), body.strip()))
    return hashlib.sha256(raw.encode()).hexdigest()


def compose(
    ctx: WeddingContext,
    *,
    category: str,
    vendor_name: str,
    signature: str,
    extra_questions: tuple[str, ...] = (),
) -> tuple[str, str, list[dict[str, str]]]:
    """Zwraca (temat, treść, ujawniane dane). Budżetu pary w treści nie ma."""
    label = CATEGORIES[category][0].lower()
    when = ctx.date_label or "w terminie do ustalenia"
    disclosed: list[dict[str, str]] = [{"label": "Podpis", "value": signature}]
    facts: list[str] = []
    if ctx.date_label:
        facts.append(f"termin: {ctx.date_label}")
        disclosed.append({"label": "Termin ślubu", "value": ctx.date_label})
    if ctx.city:
        facts.append(f"miejscowość: {ctx.city}")
        disclosed.append({"label": "Miejscowość", "value": ctx.city})
    if ctx.guest_count:
        facts.append(f"liczba gości: ok. {ctx.guest_count}")
        disclosed.append({"label": "Liczba gości", "value": f"ok. {ctx.guest_count}"})
    subject = f"Zapytanie o ofertę ({label}) — ślub {when}"[:200]
    questions = [*DEFAULT_QUESTIONS, *extra_questions][:10]
    lines = [
        "Dzień dobry,",
        "",
        f"planujemy ślub i wesele ({'; '.join(facts) if facts else 'szczegóły do ustalenia'}) "
        f"i chcielibyśmy zapytać o Państwa usługę: {label} ({vendor_name}).",
        "",
        "Będziemy wdzięczni za odpowiedź na pytania:",
        *[f"{i}. {q}" for i, q in enumerate(questions, start=1)],
        "",
        "Jeśli któraś informacja zależy od szczegółów, prosimy o wskazanie, czego brakuje do wyceny.",
        "",
        "Pozdrawiamy",
        signature,
        "",
        "—",
        "Wiadomość wysłana przez parę za pośrednictwem aplikacji „Nasz dzień”. Jeśli nie chcą "
        "Państwo otrzymywać takich zapytań, prosimy o odpowiedź z taką informacją.",
    ]
    return subject, "\n".join(lines), disclosed


def budget_warnings(body: str, subject: str, amounts: list[Decimal]) -> list[str]:
    """Ostrzeżenia: treść wygląda na ujawniającą budżet pary (domyślnie tego nie robimy)."""
    text = f"{subject}\n{body}"
    warnings: list[str] = []
    if re.search(r"bud[żz]et", text, re.IGNORECASE):
        warnings.append("W treści jest słowo „budżet”. Domyślnie nie ujawniamy budżetu firmie.")
    digits = re.sub(r"[\s .]", "", text)
    for amount in amounts:
        whole = f"{amount:.0f}"
        if len(whole) >= 4 and re.search(rf"(?<!\d){whole}(?!\d)", digits):
            warnings.append(
                f"W treści jest kwota {whole}, która wygląda jak Wasz budżet. Czy to zamierzone?"
            )
            break
    return warnings
