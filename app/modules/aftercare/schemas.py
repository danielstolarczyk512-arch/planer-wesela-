from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import Money, PatchModel


class DeliverableCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120, examples=["Zdjęcia — galeria online"])
    vendor_id: UUID | None = None
    due_on: date | None = Field(default=None, description="Termin z umowy")
    note: str | None = Field(default=None, max_length=2000)


class DeliverableUpdate(PatchModel):
    NOT_NULL = ("title",)

    title: str | None = Field(default=None, min_length=1, max_length=120)
    vendor_id: UUID | None = None
    due_on: date | None = None
    received_on: date | None = None
    note: str | None = Field(default=None, max_length=2000)


class DeliverableOut(BaseModel):
    id: UUID
    vendor_id: UUID | None
    vendor_name: str | None
    title: str
    due_on: date | None
    received_on: date | None
    note: str | None
    status: Literal["waiting", "overdue", "received"]
    days_late: int
    version: int


class OpenPayment(BaseModel):
    id: UUID
    item_name: str
    amount: Money
    due_date: date | None
    overdue: bool


class NameChangeOut(BaseModel):
    code: str
    title: str
    hint: str
    source: str | None
    approx_deadline: date | None = Field(
        description="Orientacyjnie (liczone od dnia ślubu; termin biegnie od zmiany w PESEL)"
    )
    done_on: date | None


class ThanksOut(BaseModel):
    with_gift: int
    thanked_with_gift: int
    thanked: int


class AfterWedding(BaseModel):
    wedding_day: date | None
    after_wedding: bool
    open_payments: list[OpenPayment]
    deliverables: list[DeliverableOut]
    name_change: list[NameChangeOut]
    thanks: ThanksOut


class CheckIn(BaseModel):
    done: bool
