"""Widoki przekrojowe wesela: podsumowanie (pulpit) i pełny eksport danych (RODO)."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.db import utcnow
from app.modules.aftercare.models import AfterCheck, Deliverable
from app.modules.audit import service as audit
from app.modules.budget import service as budget
from app.modules.budget.models import (
    BudgetCategory,
    BudgetItem,
    Funder,
    FunderContribution,
    Payment,
)
from app.modules.concierge.models import (
    Candidate,
    Conversation,
    DiscoveryRequest,
    Message,
    VendorPreferences,
)
from app.modules.documents.models import Document, DocumentVersion
from app.modules.guests import service as guests
from app.modules.guests.models import (
    GiftIdea,
    Guest,
    GuestEventAttendance,
    GuestWish,
    Household,
    ReserveEntry,
)
from app.modules.identity.models import User
from app.modules.identity.service import Principal
from app.modules.inquiries.models import IncomingMessage, Inquiry, InquiryRevision, MailDelivery
from app.modules.logistics.models import LodgingRoom, RoomGuest, TransportRun, TransportSeat
from app.modules.menu.models import MenuDish
from app.modules.offers.models import Offer, OfferTerm, PricingComponent
from app.modules.planner import service as planner
from app.modules.planner.models import (
    CeremonyDocument,
    Helper,
    Task,
    TaskComment,
    TaskDependency,
)
from app.modules.schedule import service as schedule
from app.modules.schedule.models import (
    DayChecklistItem,
    MusicEntry,
    PhotoGroup,
    PhotoGroupGuest,
    PrepPerson,
    PrepPlan,
    VendorBrief,
)
from app.modules.seating import service as seating
from app.modules.vendors.models import Vendor
from app.modules.workspace.models import Event, Wedding, WeddingMember
from app.modules.workspace.permissions import Action, authorize


def summary(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    wedding = db.get_one(Wedding, wedding_id)
    today = clock.today()
    anchor = planner.wedding_anchor(wedding)
    tasks = list(db.scalars(select(Task).where(Task.wedding_id == wedding_id)))
    # Podzadania (np. pozycje listy dokumentów) liczą się w zadaniu nadrzędnym.
    tasks = [t for t in tasks if t.parent_task_id is None]
    open_tasks = [t for t in tasks if t.status in planner.OPEN_STATUSES]
    soon = sorted(
        (t for t in open_tasks if t.due_date and today <= t.due_date <= today + timedelta(days=14)),
        key=lambda t: (t.due_date, t.priority),
    )
    b = budget.overview(db, principal, wedding_id)
    counts = b["guest_counts"]
    return {
        "wedding": {
            "id": wedding.id,
            "name": wedding.name,
            "wedding_date": wedding.wedding_date,
            "planned_month": wedding.planned_month.strftime("%Y-%m")
            if wedding.planned_month
            else None,
            "days_to_wedding": (anchor - today).days if anchor else None,
        },
        "tasks": {
            "total": len(tasks),
            "done": sum(1 for t in tasks if t.status == "done"),
            "open": len(open_tasks),
            "overdue": sum(1 for t in open_tasks if planner.is_overdue(t)),
            "due_next_14_days": [
                {"id": t.id, "title": t.title, "due_date": t.due_date, "priority": t.priority}
                for t in soon[:10]
            ],
        },
        "budget": {
            "total_budget": wedding.total_budget,
            "estimated_total": b["estimated_total"],
            "paid_total": b["paid_total"],
            "remaining_to_pay": b["remaining_to_pay"],
            "over_budget": b["over_budget"],
            "overdue_payments": len(b["overdue_payments"]),
            "upcoming_payments_30d": len(b["upcoming_payments_30d"]),
        },
        "guests": {
            **counts,
            "pending_answers": max(
                counts["invited"] - counts["confirmed"] - _declined(db, wedding_id), 0
            ),
        },
    }


def _declined(db: Session, wedding_id: UUID) -> int:
    """Liczba gości, którzy odmówili udziału w przyjęciu."""
    reception = list(
        db.scalars(
            select(Event.id).where(Event.wedding_id == wedding_id, Event.kind == "reception")
        )
    )
    if not reception:
        return 0
    return len(
        set(
            db.scalars(
                select(GuestEventAttendance.guest_id).where(
                    GuestEventAttendance.event_id.in_(reception),
                    GuestEventAttendance.status == "declined",
                )
            )
        )
    )


def _row(obj: Any, exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for column in obj.__table__.columns:
        if column.key in exclude:
            continue
        value = getattr(obj, column.key)
        if isinstance(value, bool | int | str | dict | list | type(None)):
            out[column.key] = value  # JSONB (dict/list) zostaje strukturą, nie tekstem
        else:
            out[column.key] = str(value)  # Decimal, data, UUID → tekst
    return out


def export_wedding(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    """Pełny eksport danych wesela (art. 15 i 20 RODO). Zawiera odszyfrowane uwagi dietetyczne."""
    authorize(db, principal.user.id, wedding_id, Action.EXPORT)
    wedding = db.get_one(Wedding, wedding_id)
    members = db.execute(
        select(WeddingMember, User.email, User.display_name)
        .join(User, User.id == WeddingMember.user_id)
        .where(WeddingMember.wedding_id == wedding_id)
    ).all()
    task_ids = list(db.scalars(select(Task.id).where(Task.wedding_id == wedding_id)))
    guest_list = list(db.scalars(select(Guest).where(Guest.wedding_id == wedding_id)))
    att = guests.attendance_map(db, [g.id for g in guest_list])

    def by_wedding(model: Any) -> list[Any]:
        return list(db.scalars(select(model).where(model.wedding_id == wedding_id)))

    schedule_items = schedule.items_of(db, wedding_id)
    schedule_deps = schedule.dependencies(db, [i.id for i in schedule_items])

    data = {
        "exported_at": utcnow().isoformat(),
        "format_version": 1,
        "wedding": _row(wedding),
        "events": [_row(e) for e in by_wedding(Event)],
        "members": [
            {
                "user_id": str(m.user_id),
                "email": email,
                "display_name": name,
                "role": m.role,
                "joined_at": m.joined_at.isoformat(),
            }
            for m, email, name in members
        ],
        "tasks": [_row(t) for t in by_wedding(Task)],
        "task_dependencies": [
            {"task_id": str(d.task_id), "depends_on_task_id": str(d.depends_on_task_id)}
            for d in db.scalars(select(TaskDependency).where(TaskDependency.task_id.in_(task_ids)))
        ]
        if task_ids
        else [],
        "budget": {
            "categories": [_row(c) for c in by_wedding(BudgetCategory)],
            "items": [_row(i) for i in by_wedding(BudgetItem)],
            "payments": [_row(p) for p in by_wedding(Payment)],
            "funders": [_row(f) for f in by_wedding(Funder)],
            "funder_contributions": [_row(c) for c in by_wedding(FunderContribution)],
        },
        "vendors": [_row(v) for v in by_wedding(Vendor)],
        "offers": [
            {
                **_row(o),
                "components": [
                    _row(c)
                    for c in db.scalars(
                        select(PricingComponent).where(PricingComponent.offer_id == o.id)
                    )
                ],
                "terms": [
                    _row(t) for t in db.scalars(select(OfferTerm).where(OfferTerm.offer_id == o.id))
                ],
            }
            for o in by_wedding(Offer)
        ],
        "documents": [
            {
                **_row(d),
                "versions": [
                    _row(v, exclude=("storage_key",))
                    for v in db.scalars(
                        select(DocumentVersion).where(DocumentVersion.document_id == d.id)
                    )
                ],
                "note": "Pliki: GET /weddings/{id}/documents/{doc}/versions/{ver}/file",
            }
            for d in by_wedding(Document)
        ],
        "schedule": [
            {**_row(i), "depends_on": [str(d) for d in schedule_deps[i.id]]} for i in schedule_items
        ],
        "seating": {
            "tables": [_row(t) for t in seating.tables_of(db, wedding_id)],
            "assignments": [_row(a) for a in seating.assignments_of(db, wedding_id)],
            "rules": [_row(r) for r in seating.rules_of(db, wedding_id)],
        },
        "households": [_row(h) for h in by_wedding(Household)],
        "reserve_list": [_row(e) for e in by_wedding(ReserveEntry)],
        "ceremony_documents": [_row(d) for d in by_wedding(CeremonyDocument)],
        "day_checklist": [_row(i) for i in by_wedding(DayChecklistItem)],
        "music": [_row(m) for m in by_wedding(MusicEntry)],
        "menu": [_row(d) for d in by_wedding(MenuDish)],
        "guest_wishes": [_row(w) for w in by_wedding(GuestWish)],
        "gift_ideas": [_row(g) for g in by_wedding(GiftIdea)],
        "task_comments": [_row(c) for c in by_wedding(TaskComment)],
        # Pomocnicy bez hasha tokenu (link nie trafia do eksportu).
        "helpers": [
            {k: v for k, v in _row(h).items() if k != "token_hash"} for h in by_wedding(Helper)
        ],
        "prep_people": [_row(p) for p in by_wedding(PrepPerson)],
        "prep_plan": [_row(p) for p in by_wedding(PrepPlan)],
        "photo_groups": [
            {
                **_row(g),
                "guest_ids": [
                    str(i)
                    for i in db.scalars(
                        select(PhotoGroupGuest.guest_id).where(PhotoGroupGuest.group_id == g.id)
                    )
                ],
            }
            for g in by_wedding(PhotoGroup)
        ],
        "deliverables": [_row(d) for d in by_wedding(Deliverable)],
        "after_checks": [_row(c) for c in by_wedding(AfterCheck)],
        "transport_runs": [
            {
                **_row(r),
                "guest_ids": [
                    str(s.guest_id)
                    for s in db.scalars(select(TransportSeat).where(TransportSeat.run_id == r.id))
                ],
            }
            for r in by_wedding(TransportRun)
        ],
        "lodging_rooms": [
            {
                **_row(r),
                "guest_ids": [
                    str(o.guest_id)
                    for o in db.scalars(select(RoomGuest).where(RoomGuest.room_id == r.id))
                ],
            }
            for r in by_wedding(LodgingRoom)
        ],
        "vendor_briefs": [_row(b) for b in by_wedding(VendorBrief)],
        # Dobór usługodawców (etapy 2-3): preferencje, rozmowy z asystentem, kandydaci, zapytania.
        "vendor_search": {
            "preferences": [_row(p) for p in by_wedding(VendorPreferences)],
            "candidates": [_row(c) for c in by_wedding(Candidate)],
            "discovery_requests": [_row(r) for r in by_wedding(DiscoveryRequest)],
            "conversations": [
                {
                    **_row(c),
                    "messages": [
                        _row(m)
                        for m in db.scalars(
                            select(Message)
                            .where(Message.conversation_id == c.id)
                            .order_by(Message.created_at)
                        )
                    ],
                }
                for c in by_wedding(Conversation)
            ],
        },
        "inquiries": [
            {
                **_row(i),
                "revisions": [
                    _row(r)
                    for r in db.scalars(
                        select(InquiryRevision)
                        .where(InquiryRevision.inquiry_id == i.id)
                        .order_by(InquiryRevision.number)
                    )
                ],
                "deliveries": [
                    _row(d)
                    for d in db.scalars(select(MailDelivery).where(MailDelivery.inquiry_id == i.id))
                ],
                "responses": [
                    _row(r)
                    for r in db.scalars(
                        select(IncomingMessage).where(IncomingMessage.inquiry_id == i.id)
                    )
                ],
            }
            for i in by_wedding(Inquiry)
        ],
        "guests": [
            {
                **_row(g, exclude=("dietary_note_encrypted",)),
                "dietary_note": guests.dietary_note(g),
                "attendance": {str(k): v for k, v in att[g.id].items()},
            }
            for g in guest_list
        ],
    }
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="wedding",
        entity_id=wedding_id,
        wedding_id=wedding_id,
        action="export",
    )
    db.commit()
    return data
