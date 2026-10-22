"""Licznik ważności dokumentów do ślubu: okna „najwcześniej / najpóźniej” liczone od daty ślubu.

Zasady pochodzą ze źródeł podanych przy każdej pozycji. Terminy urzędowe są na gov.pl, a kościelne
różnią się między parafiami, więc mają wartość domyślną, którą para może zmienić. Aplikacja
informuje, nie udziela porady prawnej: każda pozycja ma dopisek, by potwierdzić termin w USC
lub parafii.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import NotFound, Unprocessable
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.planner.models import CeremonyDocument
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

GOV_CIVIL = "https://www.gov.pl/web/gov/wez-slub-cywilny"
GOV_RELIGIOUS = "https://www.gov.pl/web/gov/wez-slub-wyznaniowy"
PARISH_EXAMPLE = "https://dr.diecezjatarnow.pl/niezbedne-dokumenty"


@dataclass(frozen=True)
class DocRule:
    code: str
    title: str
    ceremonies: tuple[str, ...]
    # Ważność w miesiącach od wydania (None: dokument/spotkanie bez terminu ważności).
    valid_months: int | None
    # Najpóźniej: tyle dni przed ślubem (None: bez dolnej granicy poza ważnością).
    latest_days_before: int | None
    hint: str
    source: str
    source_label: str
    editable_validity: bool = False


RULES: tuple[DocRule, ...] = (
    DocRule(
        "usc_assurance",
        "Zapewnienie w USC o braku przeszkód do małżeństwa",
        ("civil",),
        valid_months=6,
        latest_days_before=31,
        hint="Ślub można zawrzeć po upływie miesiąca od złożenia zapewnienia, a zapewnienie jest "
        "ważne 6 miesięcy. Dokładny dzień potwierdźcie w USC.",
        source=GOV_CIVIL,
        source_label="gov.pl: Weź ślub cywilny",
    ),
    DocRule(
        "usc_certificate",
        "Zaświadczenie z USC do ślubu kościelnego (wyznaniowego)",
        ("concordat", "religious_other"),
        valid_months=6,
        latest_days_before=30,
        hint="Zaświadczenie jest ważne 6 miesięcy. Parafia zwykle potrzebuje go przed ślubem — "
        "zapytajcie w kancelarii, do kiedy je dostarczyć.",
        source=GOV_RELIGIOUS,
        source_label="gov.pl: Weź ślub wyznaniowy",
    ),
    DocRule(
        "baptism",
        "Świadectwo chrztu do ślubu",
        ("concordat",),
        valid_months=6,
        latest_days_before=90,
        hint="Parafie wymagają świadectwa wydanego niedawno — często nie wcześniej niż "
        "6 (czasem 3) "
        "miesiące przed ślubem. Ważność ustawcie wg swojej parafii. Nie jest potrzebne, gdy ślub "
        "jest w parafii chrztu.",
        source=PARISH_EXAMPLE,
        source_label="przykład: Diecezja Tarnowska — niezbędne dokumenty",
        editable_validity=True,
    ),
    DocRule(
        "parish_protocol",
        "Zgłoszenie w kancelarii parafialnej (protokół przedmałżeński)",
        ("concordat",),
        valid_months=None,
        latest_days_before=90,
        hint="Narzeczeni zgłaszają się zwykle najpóźniej 3 miesiące przed ślubem. Termin ustalcie "
        "w swojej parafii.",
        source=PARISH_EXAMPLE,
        source_label="przykład: Diecezja Tarnowska — przygotowanie do małżeństwa",
    ),
)
BY_CODE = {r.code: r for r in RULES}


def add_months(d: date, months: int) -> date:
    """Data przesunięta o miesiące (31 stycznia + 1 miesiąc → koniec lutego)."""
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def evaluate(
    rule: DocRule,
    wedding_day: date | None,
    today: date,
    *,
    issued_on: date | None = None,
    done: bool = False,
    valid_months: int | None = None,
) -> dict[str, Any]:
    """Okno i stan jednego dokumentu. Statusy: no_date, too_early, now, late, ok, expires, done."""
    months = valid_months if valid_months is not None else rule.valid_months
    earliest = add_months(wedding_day, -months) if wedding_day and months else None
    latest = (
        wedding_day - timedelta(days=rule.latest_days_before)
        if wedding_day and rule.latest_days_before
        else None
    )
    expires_on = add_months(issued_on, months) if issued_on and months else None
    if wedding_day is None:
        status = "no_date"
    elif issued_on and expires_on:
        status = "expires" if expires_on <= wedding_day else "ok"
    elif done or issued_on:
        status = "done"
    elif earliest and today < earliest:
        status = "too_early"
    elif latest and today > latest:
        status = "late"
    else:
        status = "now"
    return {
        "earliest": earliest,
        "latest": latest,
        "expires_on": expires_on,
        "valid_months": months,
        "status": status,
    }


def _wedding_day(wedding: Wedding) -> tuple[date | None, bool]:
    """Data ślubu i czy przybliżona (tylko planowany miesiąc → 1. dzień miesiąca)."""
    if wedding.wedding_date:
        return wedding.wedding_date, False
    if wedding.planned_month:
        return wedding.planned_month, True
    return None, False


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return summary_for(db, wedding_id)


def attention(db: Session, wedding_id: UUID) -> list[str]:
    """Wiersze do podsumowania e-mail: dokumenty po terminie lub tracące ważność przed ślubem."""
    out = []
    for i in summary_for(db, wedding_id)["items"]:
        if i["status"] == "expires" and i["expires_on"]:
            out.append(f"{i['title']}: straci ważność {i['expires_on']:%d.%m.%Y}, przed ślubem")
        elif i["status"] == "late":
            out.append(f"{i['title']}: po zalecanym terminie")
    return out


def summary_for(db: Session, wedding_id: UUID) -> dict[str, Any]:
    wedding = db.get_one(Wedding, wedding_id)
    day, approximate = _wedding_day(wedding)
    saved = {
        d.code: d
        for d in db.scalars(
            select(CeremonyDocument).where(CeremonyDocument.wedding_id == wedding_id)
        )
    }
    today = clock.today()
    items = []
    for rule in RULES:
        if wedding.ceremony_type not in rule.ceremonies:
            continue
        s = saved.get(rule.code)
        items.append(
            {
                "code": rule.code,
                "title": rule.title,
                "hint": rule.hint,
                "source": rule.source,
                "source_label": rule.source_label,
                "has_validity": rule.valid_months is not None,
                "editable_validity": rule.editable_validity,
                "issued_on": s.issued_on if s else None,
                "done": s.done if s else False,
                **evaluate(
                    rule,
                    day,
                    today,
                    issued_on=s.issued_on if s else None,
                    done=s.done if s else False,
                    valid_months=s.valid_months if s else None,
                ),
            }
        )
    items.sort(key=lambda i: (i["earliest"] or i["latest"] or date.max, i["code"]))
    return {
        "ceremony_type": wedding.ceremony_type,
        "wedding_day": day,
        "approximate": approximate,
        "items": items,
    }


def save(
    db: Session, principal: Principal, wedding_id: UUID, code: str, data: dict[str, Any]
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    rule = BY_CODE.get(code)
    if rule is None:
        raise NotFound("Nie ma takiego dokumentu.", code="ceremony_document.not_found")
    if data.get("valid_months") is not None and not rule.editable_validity:
        raise Unprocessable(
            "Ważności tego dokumentu nie zmienia się (wynika z przepisów).",
            code="ceremony_document.validity_fixed",
        )
    if data.get("issued_on") is not None and rule.valid_months is None:
        raise Unprocessable(
            "Ta pozycja nie ma daty wydania — zaznaczcie ją jako zrobioną.",
            code="ceremony_document.no_issue_date",
        )
    doc = db.get(CeremonyDocument, (wedding_id, code))
    if doc is None:
        doc = CeremonyDocument(wedding_id=wedding_id, code=code)
        db.add(doc)
    doc.issued_on, doc.done, doc.valid_months = (
        data.get("issued_on"),
        bool(data.get("done")),
        data.get("valid_months"),
    )
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="ceremony_document",
        entity_id=wedding_id,
        wedding_id=wedding_id,
        action="update",
        changes={"code": code},
    )
    db.commit()
