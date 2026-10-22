"""„Wymaga uwagi”: najważniejsze ostrzeżenia z całego wesela w jednym miejscu (ekran Dziś).

Nowe moduły (frekwencja, dokumenty, waloryzacja, usługodawcy, transport, zaproszenia, po weselu)
mają własne ekrany. Para nie zagląda do wszystkich codziennie, więc zbieramy tu to, co wymaga
działania, z linkiem do właściwego ekranu. Bez nowych danych: tylko odczyt istniejących modułów.
"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import clock
from app.modules.identity.service import Principal
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
LIMIT = 8
VENDOR_ACK_DAYS = 14


def _item(code: str, severity: str, message: str, link: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message, "link": link}


def attention(db: Session, principal: Principal, wedding_id: UUID) -> list[dict[str, str]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    # Importy lokalne: przegląd czyta inne moduły, one nie zależą od niego.
    from app.modules.aftercare import service as aftercare
    from app.modules.budget import indexation
    from app.modules.guests import delivery, forecast
    from app.modules.logistics import service as logistics
    from app.modules.planner import documents
    from app.modules.schedule import briefs

    wedding = db.get_one(Wedding, wedding_id)
    today = clock.today()
    out: list[dict[str, str]] = []

    f = forecast.build(db, principal, wedding_id)
    for a in f["alerts"]:
        severity = (
            "error" if a["code"] in ("final_count.overdue", "guests.over_planned") else "warning"
        )
        out.append(_item(a["code"], severity, a["message"], "frekwencja"))

    for d in documents.overview(db, principal, wedding_id)["items"]:
        if d["status"] == "expires":
            out.append(
                _item(
                    "documents.expires",
                    "error",
                    f"{d['title']}: straci ważność {d['expires_on']:%d.%m.%Y}, przed ślubem.",
                    "formalnosci",
                )
            )
        elif d["status"] == "late":
            out.append(
                _item(
                    "documents.late",
                    "warning",
                    f"{d['title']}: po zalecanym terminie.",
                    "formalnosci",
                )
            )

    for r in indexation.overview(db, principal, wedding_id)["reviews_soon"]:
        out.append(
            _item(
                "budget.price_review",
                "warning",
                f"{r['name']}: termin aneksu lub potwierdzenia ceny "
                f"{r['price_review_on']:%d.%m.%Y}.",
                "budzet",
            )
        )

    after = aftercare.overview(db, principal, wedding_id)
    for d in after["deliverables"]:
        if d["status"] == "overdue":
            out.append(
                _item(
                    "deliverable.overdue",
                    "warning",
                    f"{d['title']}: spóźnienie {d['days_late']} dni.",
                    "po-weselu",
                )
            )

    day = wedding.wedding_date
    if day and today <= day <= today + timedelta(days=VENDOR_ACK_DAYS):
        behind = [
            s["vendor_name"]
            for s in briefs.statuses(db, principal, wedding_id)
            if not s["up_to_date"]
        ]
        if behind:
            out.append(
                _item(
                    "vendors.not_acknowledged",
                    "warning",
                    "Aktualnego programu nie potwierdzili: " + ", ".join(behind) + ".",
                    "dzien",
                )
            )

    log = logistics.overview(db, principal, wedding_id)
    for r in log["runs"]:
        if r["over"]:
            out.append(
                _item(
                    "transport.over",
                    "error",
                    f"Kurs „{r['name']}” jest przepełniony o {r['over']} os.",
                    "logistyka",
                )
            )
    if log["runs"] and log["transport_missing"]:
        out.append(
            _item(
                "transport.missing",
                "info",
                f"Bez kursu: {len(log['transport_missing'])} os. potrzebujących transportu.",
                "logistyka",
            )
        )
    if log["rooms"] and log["lodging_missing"]:
        out.append(
            _item(
                "lodging.missing",
                "info",
                f"Bez pokoju: {len(log['lodging_missing'])} os. potrzebujących noclegu.",
                "logistyka",
            )
        )

    inv = delivery.overview(db, principal, wedding_id)
    remaining = inv["in_person_total"] - inv["in_person_delivered"]
    if remaining and inv["deadline"] and inv["deadline"] <= today + timedelta(days=30):
        out.append(
            _item(
                "invitations.remaining",
                "warning",
                f"Do wręczenia osobiście zostało {remaining} zaproszeń, "
                f"termin {inv['deadline']:%d.%m.%Y}.",
                "zaproszenia",
            )
        )

    from app.modules.budget.funders import reported_lines

    for name, amount in reported_lines(db, wedding_id):
        out.append(
            _item(
                "funder.reported",
                "info",
                f"{name}: zgłoszony przelew {amount:,.0f} zł — potwierdźcie po otrzymaniu.".replace(
                    ",", " "
                ),
                "sponsorzy",
            )
        )

    out.sort(key=lambda i: SEVERITY_ORDER[i["severity"]])
    return out[:LIMIT]
