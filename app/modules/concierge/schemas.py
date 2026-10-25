from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.modules.catalog.schemas import CatalogVendorOut
from app.modules.concierge.matching import Match
from app.modules.concierge.models import (
    Candidate,
    Conversation,
    DiscoveryRequest,
    Message,
    VendorPreferences,
)
from app.modules.vendors.schemas import VendorCategory

Term = Annotated[str, Field(min_length=1, max_length=60)]
Tag = Annotated[str, Field(min_length=1, max_length=40)]


class PreferencesIn(BaseModel):
    scope_terms: list[Term] | None = Field(default=None, max_length=8)
    style_tags: list[Tag] | None = Field(default=None, max_length=8)
    budget_max: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] | None = None
    notes: str | None = Field(default=None, max_length=1000)


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category: str
    scope_terms: list[str]
    style_tags: list[str]
    budget_max: Decimal | None
    notes: str | None
    version: int

    @field_serializer("budget_max")
    def _money(self, v: Decimal | None) -> str | None:
        return None if v is None else f"{v:.2f}"

    @classmethod
    def from_row(cls, row: VendorPreferences) -> "PreferencesOut":
        return cls(
            category=row.category,
            scope_terms=list(row.scope_terms or []),
            style_tags=list(row.style_tags or []),
            budget_max=row.budget_max,
            notes=row.notes,
            version=row.version,
        )


class SearchIn(BaseModel):
    category: VendorCategory
    limit: int = Field(default=5, ge=1, le=20)


class ReasonOut(BaseModel):
    kind: str
    text: str
    evidence: str | None
    source_url: str | None


class MatchOut(BaseModel):
    catalog_vendor_id: UUID
    vendor: CatalogVendorOut
    reasons: list[ReasonOut]
    missing: list[str]
    flags: list[str]
    region_fit: str
    budget_fit: str


def match_out(match: Match) -> MatchOut:
    from app.modules.concierge.agent import card_dict

    return MatchOut.model_validate(card_dict(match))


class SearchOut(BaseModel):
    category: str
    items: list[MatchOut]
    note: str | None = None


class CandidateIn(BaseModel):
    catalog_vendor_id: UUID
    note: str | None = Field(default=None, max_length=500)


class CandidatePatch(BaseModel):
    state: Annotated[str, Field(pattern="^(saved|rejected)$")] | None = None
    note: str | None = Field(default=None, max_length=500)


class CandidateOut(BaseModel):
    id: UUID
    catalog_vendor_id: UUID
    name: str
    category: str
    city: str | None
    state: str
    note: str | None
    reasoning: dict[str, Any]
    vendor_id: UUID | None
    created_at: datetime

    @classmethod
    def build(cls, c: Candidate, name: str, city: str | None) -> "CandidateOut":
        return cls(
            id=c.id,
            catalog_vendor_id=c.catalog_vendor_id,
            name=name,
            category=c.category,
            city=city,
            state=c.state,
            note=c.note,
            reasoning=c.reasoning or {},
            vendor_id=c.vendor_id,
            created_at=c.created_at,
        )


class CandidateCompareOut(BaseModel):
    category: str
    items: list[MatchOut]


class DiscoveryIn(BaseModel):
    category: VendorCategory
    region: str | None = Field(default=None, max_length=120)


class DiscoveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    category: str
    region: str | None
    state: str
    result: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str | None
    created_at: datetime

    @classmethod
    def of(cls, c: Conversation) -> "ConversationOut":
        return cls(id=c.id, title=c.title, created_at=c.created_at)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    role: str
    content: str
    state: str
    actions: list[dict[str, Any]]
    cards: list[dict[str, Any]]
    created_at: datetime

    @classmethod
    def of(cls, m: Message) -> "MessageOut":
        return cls(
            id=m.id,
            role=m.role,
            content=m.content,
            state=m.state,
            actions=list(m.actions or []),
            cards=list(m.cards or []),
            created_at=m.created_at,
        )


class PostedOut(BaseModel):
    user_message: MessageOut
    reply: MessageOut


__all__ = ["DiscoveryRequest"]
