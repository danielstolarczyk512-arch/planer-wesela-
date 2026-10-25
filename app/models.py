"""Rejestr wszystkich modeli: Alembic i testy importują metadane stąd."""

from app.core.db import Base
from app.core.idempotency import IdempotencyKey
from app.core.ratelimit import RateLimitHit
from app.jobs.queue import Job
from app.modules.aftercare.models import AfterCheck, Deliverable
from app.modules.ai.models import AiRun
from app.modules.audit.models import AuditLog, SecurityEvent
from app.modules.budget.models import (
    BudgetAssumptions,
    BudgetCategory,
    BudgetItem,
    Funder,
    FunderContribution,
    Payment,
)
from app.modules.calendar.models import CalendarFeedToken
from app.modules.catalog.models import (
    CatalogVendor,
    DiscoveryControl,
    DomainState,
    PublicPackage,
    ReviewItem,
    SourceObservation,
    VendorFact,
    VendorSource,
)
from app.modules.concierge.models import (
    Candidate,
    Conversation,
    DiscoveryRequest,
    Message,
    VendorPreferences,
)
from app.modules.documents.models import Document, DocumentVersion
from app.modules.guests.models import (
    GiftIdea,
    Guest,
    GuestEventAttendance,
    GuestInfo,
    GuestWish,
    Household,
    ReserveEntry,
    RsvpToken,
)
from app.modules.identity.models import (
    AuthSession,
    Consent,
    MfaRecoveryCode,
    OneTimeToken,
    User,
    UserMfa,
)
from app.modules.inquiries.models import IncomingMessage, Inquiry, InquiryRevision, MailDelivery
from app.modules.logistics.models import LodgingRoom, RoomGuest, TransportRun, TransportSeat
from app.modules.menu.models import MenuDish
from app.modules.notifications.models import DigestLog, NotificationPreference
from app.modules.offers.models import Offer, OfferTerm, PricingComponent
from app.modules.planner.models import (
    CeremonyDocument,
    Helper,
    Task,
    TaskComment,
    TaskDependency,
)
from app.modules.schedule.models import (
    DayChecklistItem,
    MusicEntry,
    PhotoGroup,
    PhotoGroupGuest,
    PrepPerson,
    PrepPlan,
    ScheduleDependency,
    ScheduleItem,
    VendorBrief,
    VendorDayLink,
)
from app.modules.seating.models import (
    SeatAssignment,
    SeatingAutoRun,
    SeatingRoom,
    SeatingRule,
    SeatingTable,
)
from app.modules.vendors.models import Vendor, VendorChecklistItem
from app.modules.workspace.models import Event, Wedding, WeddingInvitation, WeddingMember

__all__ = [
    "AfterCheck",
    "AiRun",
    "AuditLog",
    "AuthSession",
    "Base",
    "BudgetAssumptions",
    "BudgetCategory",
    "BudgetItem",
    "CalendarFeedToken",
    "Candidate",
    "CatalogVendor",
    "CeremonyDocument",
    "Consent",
    "Conversation",
    "DayChecklistItem",
    "Deliverable",
    "DigestLog",
    "DiscoveryControl",
    "DiscoveryRequest",
    "Document",
    "DocumentVersion",
    "DomainState",
    "Event",
    "Funder",
    "FunderContribution",
    "GiftIdea",
    "Guest",
    "GuestEventAttendance",
    "GuestInfo",
    "GuestWish",
    "Helper",
    "Household",
    "IdempotencyKey",
    "IncomingMessage",
    "Inquiry",
    "InquiryRevision",
    "Job",
    "LodgingRoom",
    "MailDelivery",
    "MenuDish",
    "Message",
    "MfaRecoveryCode",
    "MusicEntry",
    "NotificationPreference",
    "Offer",
    "OfferTerm",
    "OneTimeToken",
    "Payment",
    "PhotoGroup",
    "PhotoGroupGuest",
    "PrepPerson",
    "PrepPlan",
    "PricingComponent",
    "PublicPackage",
    "RateLimitHit",
    "ReserveEntry",
    "ReviewItem",
    "RoomGuest",
    "RsvpToken",
    "ScheduleDependency",
    "ScheduleItem",
    "SeatAssignment",
    "SeatingAutoRun",
    "SeatingRoom",
    "SeatingRule",
    "SeatingTable",
    "SecurityEvent",
    "SourceObservation",
    "Task",
    "TaskComment",
    "TaskDependency",
    "TransportRun",
    "TransportSeat",
    "User",
    "UserMfa",
    "Vendor",
    "VendorBrief",
    "VendorChecklistItem",
    "VendorDayLink",
    "VendorFact",
    "VendorPreferences",
    "VendorSource",
    "Wedding",
    "WeddingInvitation",
    "WeddingMember",
]
