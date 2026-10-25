from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.email import outbound_allowed
from app.modules.identity.service import Principal
from app.modules.inquiries import service
from app.modules.inquiries.models import IncomingMessage, Inquiry, InquiryRevision, MailDelivery
from app.modules.vendors.models import Vendor


class RecipientIn(BaseModel):
    catalog_vendor_id: UUID | None = None
    vendor_id: UUID | None = None
    to_email: EmailStr | None = None


class DraftsIn(BaseModel):
    recipients: list[RecipientIn] = Field(min_length=1, max_length=5)
    extra_questions: list[str] = Field(default_factory=list, max_length=3)


class EditIn(BaseModel):
    base_revision: int = Field(ge=1)
    to_email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)


class ApproveIn(BaseModel):
    revision_id: UUID
    content_hash: str = Field(min_length=64, max_length=64)
    to_email: EmailStr
    acknowledge_warnings: bool = False


class BatchApproveIn(BaseModel):
    items: list[tuple[UUID, ApproveIn]] = Field(min_length=1, max_length=5)


class ResponseIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    subject: str | None = Field(default=None, max_length=200)
    received_at: datetime | None = None


class RevisionOut(BaseModel):
    id: UUID
    number: int
    to_email: str
    subject: str
    body: str
    content_hash: str
    created_at: datetime
    approved_at: datetime | None


class DeliveryOut(BaseModel):
    state: str
    attempts: int
    accepted_at: datetime | None
    last_error: str | None
    note: str


class ResponseOut(BaseModel):
    id: UUID
    subject: str | None
    body: str
    received_at: datetime | None
    document_id: UUID | None
    version_id: UUID | None
    created_at: datetime


class InquiryOut(BaseModel):
    id: UUID
    vendor_id: UUID
    vendor_name: str
    catalog_vendor_id: UUID | None
    category: str
    status: str
    revision: RevisionOut
    revisions_count: int
    delivery: DeliveryOut | None
    warnings: list[str]
    disclosed: list[dict[str, str]]
    responses: list[ResponseOut]
    outbound_enabled: bool
    created_at: datetime


class ApproveResult(BaseModel):
    inquiry_id: UUID
    created: bool
    inquiry: InquiryOut


_DELIVERY_NOTES = {
    "queued": "Wiadomość czeka w kolejce do wysłania.",
    "sending": "Wiadomość jest właśnie przekazywana do serwera pocztowego.",
    "accepted": (
        "Przyjęta przez serwer pocztowy. To nie znaczy, że firma ją odebrała ani przeczytała."
    ),
    "failed": "Nie udało się wysłać wiadomości. Możesz poprawić zapytanie i zatwierdzić ponownie.",
    "uncertain": (
        "Nie wiadomo, czy wiadomość wyszła (awaria w trakcie wysyłki). Nie wysyłamy jej "
        "ponownie automatycznie — sprawdź u firmy albo zatwierdź nową wersję."
    ),
}


def _rev(r: InquiryRevision) -> RevisionOut:
    return RevisionOut(
        id=r.id,
        number=r.number,
        to_email=r.to_email,
        subject=r.subject,
        body=r.body,
        content_hash=r.content_hash,
        created_at=r.created_at,
        approved_at=r.approved_at,
    )


def _delivery(d: MailDelivery | None) -> DeliveryOut | None:
    if d is None:
        return None
    return DeliveryOut(
        state=d.state,
        attempts=d.attempts,
        accepted_at=d.accepted_at,
        last_error=d.last_error,
        note=_DELIVERY_NOTES[d.state],
    )


def _resp(r: IncomingMessage) -> ResponseOut:
    return ResponseOut(
        id=r.id,
        subject=r.subject,
        body=r.body,
        received_at=r.received_at,
        document_id=r.document_id,
        version_id=r.version_id,
        created_at=r.created_at,
    )


def build(db: Session, principal: Principal, inquiry: Inquiry) -> InquiryOut:
    latest = service.latest_revision(db, inquiry)
    delivery = service.delivery_of(db, latest.id)
    vendor = db.get_one(Vendor, inquiry.vendor_id)
    editable = delivery is None
    return InquiryOut(
        id=inquiry.id,
        vendor_id=inquiry.vendor_id,
        vendor_name=vendor.name,
        catalog_vendor_id=inquiry.catalog_vendor_id,
        category=inquiry.category,
        status=service.status_of(db, inquiry),
        revision=_rev(latest),
        revisions_count=inquiry.latest_revision_no,
        delivery=_delivery(delivery),
        warnings=service.warnings_for(db, inquiry.wedding_id, latest) if editable else [],
        disclosed=service.disclosed_for(db, principal, inquiry.wedding_id) if editable else [],
        responses=[_resp(r) for r in service.responses_of(db, inquiry.id)],
        outbound_enabled=outbound_allowed(),
        created_at=inquiry.created_at,
    )


__all__ = ["Any"]
