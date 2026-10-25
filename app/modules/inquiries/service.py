# ruff: noqa: E501
"""Zapytania do firm: szkic → zatwierdzenie → kolejka wysyłki → odpowiedź → szkic oferty.

Najważniejsze gwarancje (pakiet „agenci weselni”, etap 3):
- bez zatwierdzenia nic nie wychodzi: wysyłka jest osobną akcją pary na konkretnej rewizji;
- zmiana adresata lub treści tworzy nową rewizję (stara zgoda nie obowiązuje);
- podwójne kliknięcie i ponowione żądanie nie tworzą dwóch dostaw (blokada wiersza + klucz
  unikalny na rewizję);
- niepewny wynik SMTP (awaria po przyjęciu) nie jest ponawiany automatycznie.
"""

import io
from datetime import timedelta
from decimal import Decimal
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any
from uuid import UUID

import structlog
from docx import Document as DocxDocument
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.email import (
    DeliveryRejected,
    DeliveryTemporary,
    DeliveryUncertain,
    deliver,
    outbound_allowed,
)
from app.core.errors import Conflict, NotFound, RateLimited, Unprocessable
from app.jobs.queue import enqueue
from app.modules.ai import service as ai
from app.modules.audit import service as audit
from app.modules.catalog import service as catalog
from app.modules.concierge import service as concierge
from app.modules.concierge.models import Candidate, VendorPreferences
from app.modules.documents import service as documents
from app.modules.identity.service import Principal
from app.modules.inquiries import templates
from app.modules.inquiries.models import (
    IncomingMessage,
    Inquiry,
    InquiryRevision,
    MailDelivery,
)
from app.modules.vendors.models import Vendor
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

log = structlog.get_logger()

SEND_JOB = "inquiry_send"
MAX_RESPONSE_CHARS = 20_000


# --- pomocnicze -----------------------------------------------------------------------------


def _inquiry(db: Session, wedding_id: UUID, inquiry_id: UUID, *, lock: bool = False) -> Inquiry:
    query = select(Inquiry).where(Inquiry.id == inquiry_id, Inquiry.wedding_id == wedding_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        raise NotFound("Nie znaleziono zapytania.", code="inquiry.not_found")
    return row


def revisions_of(db: Session, inquiry_id: UUID) -> list[InquiryRevision]:
    return list(
        db.scalars(
            select(InquiryRevision)
            .where(InquiryRevision.inquiry_id == inquiry_id)
            .order_by(InquiryRevision.number)
        )
    )


def latest_revision(db: Session, inquiry: Inquiry) -> InquiryRevision:
    return db.scalars(
        select(InquiryRevision).where(
            InquiryRevision.inquiry_id == inquiry.id,
            InquiryRevision.number == inquiry.latest_revision_no,
        )
    ).one()


def delivery_of(db: Session, revision_id: UUID) -> MailDelivery | None:
    return db.scalar(select(MailDelivery).where(MailDelivery.revision_id == revision_id))


def _budget_amounts(db: Session, wedding_id: UUID) -> list[Decimal]:
    wedding = db.get(Wedding, wedding_id)
    amounts: list[Decimal] = []
    if wedding is not None and wedding.total_budget:
        amounts.append(wedding.total_budget)
    amounts.extend(
        db.scalars(
            select(VendorPreferences.budget_max).where(
                VendorPreferences.wedding_id == wedding_id,
                VendorPreferences.budget_max.is_not(None),
            )
        )
    )
    return amounts


def warnings_for(db: Session, wedding_id: UUID, revision: InquiryRevision) -> list[str]:
    return templates.budget_warnings(
        revision.body, revision.subject, _budget_amounts(db, wedding_id)
    )


def disclosed_for(db: Session, principal: Principal, wedding_id: UUID) -> list[dict[str, str]]:
    """Co firma zobaczy w wiadomości (z szablonu) oraz adres do odpowiedzi."""
    ctx = concierge.wedding_context(db, wedding_id)
    wedding = db.get_one(Wedding, wedding_id)
    items = [{"label": "Podpis", "value": wedding.name}]
    if ctx.date_label:
        items.append({"label": "Termin ślubu", "value": ctx.date_label})
    if ctx.city:
        items.append({"label": "Miejscowość", "value": ctx.city})
    if ctx.guest_count:
        items.append({"label": "Liczba gości", "value": f"ok. {ctx.guest_count}"})
    items.append({"label": "Adres do odpowiedzi (Reply-To)", "value": principal.user.email})
    return items


# --- tworzenie i edycja ---------------------------------------------------------------------


def _recipient_email(db: Session, vendor: Vendor, catalog_vendor_id: UUID | None) -> str | None:
    if vendor.email:
        return vendor.email
    if catalog_vendor_id is not None:
        card = catalog.get_published(db, catalog_vendor_id)
        return next((f.value for f in card.facts if f.field == "email"), None)
    return None


def _ensure_private_vendor(
    db: Session, principal: Principal, wedding_id: UUID, catalog_vendor_id: UUID
) -> Vendor:
    cand = db.scalar(
        select(Candidate).where(
            Candidate.wedding_id == wedding_id, Candidate.catalog_vendor_id == catalog_vendor_id
        )
    )
    if cand is None or cand.state != "saved":
        cand = concierge.save_candidate(db, principal, wedding_id, catalog_vendor_id, None)
    if cand.vendor_id is None:
        cand = concierge.candidate_to_vendor(db, principal, wedding_id, cand.id)
    if cand.vendor_id is None:  # pragma: no cover - candidate_to_vendor zawsze ustawia
        raise NotFound("Nie znaleziono usługodawcy.", code="vendor.not_found")
    return db.get_one(Vendor, cand.vendor_id)


def create_drafts(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    recipients: list[dict[str, Any]],
    extra_questions: tuple[str, ...] = (),
) -> list[Inquiry]:
    """Szkice zapytań (po jednym na firmę). Niczego nie wysyła."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    if not 1 <= len(recipients) <= 5:
        raise Unprocessable("Wybierz od 1 do 5 firm.", code="inquiry.recipient_count")
    ctx = concierge.wedding_context(db, wedding_id)
    wedding = db.get_one(Wedding, wedding_id)
    created: list[Inquiry] = []
    seen: set[UUID] = set()
    for rec in recipients:
        catalog_id = rec.get("catalog_vendor_id")
        if catalog_id is not None:
            vendor = _ensure_private_vendor(db, principal, wedding_id, catalog_id)
        else:
            if rec.get("vendor_id") is None:
                raise Unprocessable(
                    "Wskaż firmę z katalogu albo własnego usługodawcę.",
                    code="inquiry.no_recipient",
                )
            found = db.get(Vendor, rec["vendor_id"])
            if found is None or found.wedding_id != wedding_id:
                raise NotFound("Nie znaleziono usługodawcy.", code="vendor.not_found")
            vendor = found
        if vendor.id in seen:
            continue
        seen.add(vendor.id)
        to_email = (rec.get("to_email") or _recipient_email(db, vendor, catalog_id) or "").strip()
        if not to_email:
            raise Unprocessable(
                f"Brak publicznego adresu e-mail firmy „{vendor.name}”. Podaj adres albo skopiuj "
                "treść i wyślij ją sam.",
                code="inquiry.no_recipient_email",
            )
        subject, body, _ = templates.compose(
            ctx,
            category=vendor.category,
            vendor_name=vendor.name,
            signature=wedding.name,
            extra_questions=extra_questions,
        )
        inquiry = Inquiry(
            wedding_id=wedding_id,
            vendor_id=vendor.id,
            catalog_vendor_id=catalog_id or vendor.catalog_vendor_id,
            category=vendor.category,
            created_by=principal.user.id,
        )
        db.add(inquiry)
        db.flush()
        db.add(
            InquiryRevision(
                inquiry_id=inquiry.id,
                wedding_id=wedding_id,
                number=1,
                to_email=to_email.lower(),
                subject=subject,
                body=body,
                content_hash=templates.content_hash(to_email, subject, body),
                author_id=principal.user.id,
            )
        )
        audit.record(
            db,
            actor_type="user",
            actor_id=principal.user.id,
            entity_type="inquiry",
            entity_id=inquiry.id,
            wedding_id=wedding_id,
            action="draft",
        )
        created.append(inquiry)
    db.commit()
    return created


def edit(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    inquiry_id: UUID,
    *,
    base_revision: int,
    to_email: str,
    subject: str,
    body: str,
) -> InquiryRevision:
    """Nowa rewizja. Poprzednia zgoda nie przechodzi na zmienioną treść ani adresata."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    inquiry = _inquiry(db, wedding_id, inquiry_id, lock=True)
    if inquiry.latest_revision_no != base_revision:
        raise Conflict(
            "Zapytanie zmieniło się w międzyczasie. Odśwież ekran.",
            code="conflict.version_mismatch",
        )
    current = latest_revision(db, inquiry)
    delivery = delivery_of(db, current.id)
    if delivery is not None and delivery.state in ("queued", "sending"):
        raise Conflict(
            "Ta wiadomość jest właśnie wysyłana. Poczekaj na wynik.", code="inquiry.in_flight"
        )
    to_email = to_email.strip().lower()
    subject, body = subject.strip(), body.strip()
    if not (to_email and subject and body):
        raise Unprocessable("Adresat, temat i treść są wymagane.", code="inquiry.empty_fields")
    rev = InquiryRevision(
        inquiry_id=inquiry.id,
        wedding_id=wedding_id,
        number=inquiry.latest_revision_no + 1,
        to_email=to_email,
        subject=subject[:200],
        body=body,
        content_hash=templates.content_hash(to_email, subject[:200], body),
        author_id=principal.user.id,
    )
    db.add(rev)
    inquiry.latest_revision_no = rev.number
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="inquiry",
        entity_id=inquiry.id,
        wedding_id=wedding_id,
        action="revise",
        changes={"revision": rev.number},
    )
    db.commit()
    return rev


def delete_draft(db: Session, principal: Principal, wedding_id: UUID, inquiry_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    inquiry = _inquiry(db, wedding_id, inquiry_id, lock=True)
    sent = db.scalar(
        select(func.count()).select_from(MailDelivery).where(MailDelivery.inquiry_id == inquiry.id)
    )
    if sent:
        raise Conflict("Wysłanego zapytania nie można usunąć.", code="inquiry.already_sent")
    db.delete(inquiry)
    db.commit()


# --- zatwierdzenie i wysyłka ----------------------------------------------------------------


def approve_and_send(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    inquiry_id: UUID,
    *,
    revision_id: UUID,
    content_hash: str,
    to_email: str,
    acknowledge_warnings: bool,
) -> tuple[InquiryRevision, MailDelivery, bool]:
    """Zatwierdza konkretną rewizję i kolejkuje dostarczenie. Idempotentne.

    Zwraca (rewizja, dostarczenie, nowe). `nowe=False`, gdy ta rewizja była już zatwierdzona
    (ponowione żądanie / podwójne kliknięcie) — nic nie jest wysyłane drugi raz.
    """
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    if not outbound_allowed():
        raise Conflict(
            "Wysyłka zapytań do firm nie jest jeszcze włączona. Na razie możesz skopiować treść "
            "i wysłać ją samodzielnie.",
            code="inquiry.outbound_disabled",
        )
    inquiry = _inquiry(db, wedding_id, inquiry_id, lock=True)  # serializuje podwójne kliknięcie
    revision = db.get(InquiryRevision, revision_id)
    if revision is None or revision.inquiry_id != inquiry.id:
        raise NotFound("Nie znaleziono rewizji.", code="inquiry.revision_not_found")
    existing = delivery_of(db, revision.id)
    if existing is not None:
        return revision, existing, False
    if revision.number != inquiry.latest_revision_no:
        raise Conflict(
            "To nie jest aktualna wersja zapytania. Odśwież ekran i zatwierdź ponownie.",
            code="inquiry.stale_revision",
        )
    if revision.content_hash != content_hash or revision.to_email != to_email.strip().lower():
        raise Conflict(
            "Treść lub adresat zmieniły się po tym, jak je zobaczyłeś. Sprawdź i zatwierdź ponownie.",
            code="inquiry.content_changed",
        )
    if warnings_for(db, wedding_id, revision) and not acknowledge_warnings:
        raise Unprocessable(
            "Treść zawiera ostrzeżenia. Potwierdź, że to zamierzone.",
            code="inquiry.warnings_unacknowledged",
        )
    _check_limits(db, wedding_id, revision.to_email)
    now = utcnow()
    revision.approved_by, revision.approved_at = principal.user.id, now
    delivery = MailDelivery(
        revision_id=revision.id,
        inquiry_id=inquiry.id,
        wedding_id=wedding_id,
        to_email=revision.to_email,
        message_id=make_msgid(domain="naszdzien.invalid"),
    )
    db.add(delivery)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        found = delivery_of(db, revision_id)
        if found is None:
            raise
        return db.get_one(InquiryRevision, revision_id), found, False
    # Do kolejki trafia tylko identyfikator dostawy; treść i adresat są w niezmiennej rewizji.
    enqueue(db, SEND_JOB, {"delivery_id": str(delivery.id)}, max_attempts=2)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="inquiry",
        entity_id=inquiry.id,
        wedding_id=wedding_id,
        action="approve_send",
        changes={"revision": revision.number, "hash": revision.content_hash[:12]},
    )
    db.commit()
    return revision, delivery, True


def _check_limits(db: Session, wedding_id: UUID, to_email: str) -> None:
    settings = get_settings()
    since = utcnow() - timedelta(days=1)
    total = db.scalar(
        select(func.count())
        .select_from(MailDelivery)
        .where(MailDelivery.wedding_id == wedding_id, MailDelivery.created_at > since)
    )
    if (total or 0) >= settings.inquiry_max_sends_per_day:
        raise RateLimited(3600)
    same = db.scalar(
        select(func.count())
        .select_from(MailDelivery)
        .where(
            MailDelivery.wedding_id == wedding_id,
            MailDelivery.to_email == to_email,
            MailDelivery.created_at > since,
        )
    )
    if (same or 0) >= settings.inquiry_max_per_recipient_per_day:
        raise Conflict(
            "Do tej firmy wysłaliście już dziś kilka wiadomości. Poczekajcie na odpowiedź.",
            code="inquiry.recipient_limit",
        )


def build_message(db: Session, delivery: MailDelivery, revision: InquiryRevision) -> EmailMessage:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = delivery.to_email
    msg["Subject"] = revision.subject
    msg["Message-ID"] = delivery.message_id
    msg["Date"] = formatdate(localtime=False)
    msg["Auto-Submitted"] = "no"
    if revision.approved_by is not None:
        from app.modules.identity.models import User

        user = db.get(User, revision.approved_by)
        if user is not None:
            msg["Reply-To"] = user.email
    msg.set_content(revision.body)
    return msg


def run_send(db: Session, payload: dict[str, Any]) -> None:
    """Zadanie workera. Przyjęcie przez serwer SMTP ≠ doręczenie ani przeczytanie."""
    delivery = db.scalar(
        select(MailDelivery)
        .where(MailDelivery.id == UUID(payload["delivery_id"]))
        .with_for_update()
    )
    if delivery is None or delivery.state in ("accepted", "failed", "uncertain"):
        return
    if delivery.state == "sending":
        # Poprzednia próba została przerwana w trakcie: nie wiemy, czy serwer przyjął wiadomość.
        delivery.state, delivery.last_error = "uncertain", "przerwane w trakcie wysyłki"
        db.commit()
        return
    revision = db.get_one(InquiryRevision, delivery.revision_id)
    if revision.approved_at is None or revision.content_hash != templates.content_hash(
        revision.to_email, revision.subject, revision.body
    ):
        delivery.state, delivery.last_error = "failed", "brak ważnej zgody na tę treść"
        db.commit()
        return
    if not outbound_allowed():
        delivery.state, delivery.last_error = "failed", "wysyłka wyłączona"
        db.commit()
        return
    delivery.state = "sending"
    delivery.attempts += 1
    db.commit()  # utrwalamy „w trakcie” przed próbą: po awarii procesu stan nie zniknie
    try:
        deliver(build_message(db, delivery, revision))
    except DeliveryTemporary as exc:
        delivery.last_error = str(exc)[:200]
        if delivery.attempts >= get_settings().inquiry_send_attempts:
            delivery.state = "failed"
            db.commit()
        else:
            delivery.state = "queued"
            db.commit()
            enqueue(
                db,
                SEND_JOB,
                {"delivery_id": str(delivery.id)},
                run_after=utcnow() + timedelta(seconds=30 * 2**delivery.attempts),
                max_attempts=2,
            )
            db.commit()
        return
    except DeliveryRejected as exc:
        delivery.state, delivery.last_error = "failed", str(exc)[:200]
        db.commit()
        return
    except DeliveryUncertain as exc:
        delivery.state, delivery.last_error = "uncertain", str(exc)[:200]
        db.commit()
        return
    delivery.state, delivery.accepted_at, delivery.last_error = "accepted", utcnow(), None
    db.commit()
    log.info("inquiry_accepted", delivery_id=str(delivery.id))


# --- odpowiedzi -----------------------------------------------------------------------------


def import_response(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    inquiry_id: UUID,
    *,
    text: str,
    subject: str | None,
    received_at: Any,
) -> IncomingMessage:
    """Ręcznie wklejona odpowiedź firmy: zapis w wątku zapytania + dokument do analizy."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    inquiry = _inquiry(db, wedding_id, inquiry_id)
    text = text.strip()
    if not text or len(text) > MAX_RESPONSE_CHARS:
        raise Unprocessable(
            f"Odpowiedź musi mieć od 1 do {MAX_RESPONSE_CHARS} znaków.",
            code="inquiry.bad_response",
        )
    doc = DocxDocument()
    if subject:
        doc.add_heading(subject[:200], level=2)
    for paragraph in text.splitlines():
        doc.add_paragraph(paragraph)
    buffer = io.BytesIO()
    doc.save(buffer)
    document = documents.upload(
        db,
        principal,
        wedding_id,
        data=buffer.getvalue(),
        filename="odpowiedz-firmy.docx",
        kind="offer",
        title=f"Odpowiedź na zapytanie ({inquiry.category})",
        vendor_id=inquiry.vendor_id,
    )
    response = IncomingMessage(
        wedding_id=wedding_id,
        inquiry_id=inquiry.id,
        source="manual",
        status="assigned",
        subject=(subject or None) and subject[:200],
        body=text,
        received_at=received_at,
        document_id=document.id,
        version_id=document.current_version_id,
        created_by=principal.user.id,
    )
    db.add(response)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="inquiry",
        entity_id=inquiry.id,
        wedding_id=wedding_id,
        action="import_response",
    )
    db.commit()
    return response


def analyze_response(
    db: Session, principal: Principal, wedding_id: UUID, inquiry_id: UUID, response_id: UUID
) -> Any:
    """Istniejąca ścieżka AI: wynik to szkic oferty do zatwierdzenia (nie zmienia cennika)."""
    authorize(db, principal.user.id, wedding_id, Action.RUN_AI)
    inquiry = _inquiry(db, wedding_id, inquiry_id)
    response = db.get(IncomingMessage, response_id)
    if (
        response is None
        or response.wedding_id != wedding_id
        or response.inquiry_id != inquiry.id
        or response.document_id is None
        or response.version_id is None
    ):
        raise NotFound("Nie znaleziono odpowiedzi.", code="inquiry.response_not_found")
    return ai.request_offer_extraction(
        db, principal, wedding_id, response.document_id, response.version_id, inquiry.vendor_id
    )


# --- odczyt ---------------------------------------------------------------------------------


def status_of(db: Session, inquiry: Inquiry) -> str:
    """draft | queued | sending | sent | failed | uncertain | answered."""
    answered = db.scalar(
        select(func.count())
        .select_from(IncomingMessage)
        .where(IncomingMessage.inquiry_id == inquiry.id)
    )
    if answered:
        return "answered"
    last = latest_revision(db, inquiry)
    delivery = delivery_of(db, last.id)
    if delivery is None:
        # wcześniejsza rewizja mogła zostać wysłana — to nadal „wysłano”, a nowa to szkic zmian
        previous = db.scalar(
            select(func.count())
            .select_from(MailDelivery)
            .where(MailDelivery.inquiry_id == inquiry.id, MailDelivery.state == "accepted")
        )
        return "draft_revised" if previous else "draft"
    return {"accepted": "sent"}.get(delivery.state, delivery.state)


def list_inquiries(db: Session, principal: Principal, wedding_id: UUID) -> list[Inquiry]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return list(
        db.scalars(
            select(Inquiry)
            .where(Inquiry.wedding_id == wedding_id)
            .order_by(Inquiry.created_at.desc())
            .limit(100)
        )
    )


def get_inquiry(db: Session, principal: Principal, wedding_id: UUID, inquiry_id: UUID) -> Inquiry:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _inquiry(db, wedding_id, inquiry_id)


def responses_of(db: Session, inquiry_id: UUID) -> list[IncomingMessage]:
    return list(
        db.scalars(
            select(IncomingMessage)
            .where(IncomingMessage.inquiry_id == inquiry_id)
            .order_by(IncomingMessage.created_at)
        )
    )
