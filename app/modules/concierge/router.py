# ruff: noqa: RUF001
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response

from app.core.deps import CurrentPrincipal, DbSession, etag
from app.core.errors import PreconditionRequired, Unprocessable
from app.modules.concierge import chat, service
from app.modules.concierge.schemas import (
    CandidateCompareOut,
    CandidateIn,
    CandidateOut,
    CandidatePatch,
    ConversationOut,
    DiscoveryIn,
    DiscoveryOut,
    MessageIn,
    MessageOut,
    PostedOut,
    PreferencesIn,
    PreferencesOut,
    SearchIn,
    SearchOut,
    match_out,
)
from app.modules.vendors.models import CATEGORIES

router = APIRouter(tags=["dobór usługodawców"])
W = "/weddings/{wedding_id}"

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola tylko do odczytu"},
    409: {"description": "Konflikt"},
    422: {"description": "Błąd walidacji"},
}

IfMatchOptional = Annotated[str | None, Header(description='Wersja preferencji, np. "2"')]


def _version(if_match: str | None) -> int | None:
    if if_match is None:
        return None
    raw = if_match.strip().removeprefix("W/").strip('"')
    try:
        return int(raw)
    except ValueError as exc:
        raise Unprocessable(
            "Nieprawidłowy nagłówek If-Match.", code="precondition.invalid"
        ) from exc


# --- preferencje ----------------------------------------------------------------------------


@router.get(
    f"{W}/vendor-preferences/{{category}}", responses=_READ, summary="Preferencje kategorii"
)
def get_preferences(
    wedding_id: UUID, category: str, principal: CurrentPrincipal, db: DbSession, response: Response
) -> PreferencesOut:
    row = service.get_preferences(db, principal, wedding_id, category)
    if row is None:
        return PreferencesOut(
            category=category, scope_terms=[], style_tags=[], budget_max=None, notes=None, version=0
        )
    response.headers["ETag"] = etag(row.version)
    return PreferencesOut.from_row(row)


@router.put(
    f"{W}/vendor-preferences/{{category}}",
    responses=_WRITE,
    summary="Zapis preferencji (If-Match przy zmianie)",
)
def put_preferences(
    wedding_id: UUID,
    category: str,
    body: PreferencesIn,
    principal: CurrentPrincipal,
    db: DbSession,
    response: Response,
    if_match: IfMatchOptional = None,
) -> PreferencesOut:
    row = service.put_preferences(
        db,
        principal,
        wedding_id,
        category,
        body.model_dump(exclude_unset=True),
        _version(if_match),
    )
    response.headers["ETag"] = etag(row.version)
    return PreferencesOut.from_row(row)


# --- wyszukiwanie ręczne (bez AI) -------------------------------------------------------------


@router.post(
    f"{W}/vendor-search", responses=_READ, summary="Dobór z katalogu wg preferencji (bez AI)"
)
def vendor_search(
    wedding_id: UUID, body: SearchIn, principal: CurrentPrincipal, db: DbSession
) -> SearchOut:
    matches = service.search_for(db, principal, wedding_id, body.category, body.limit)
    note = None if matches else "Brak firm w tej kategorii w katalogu."
    return SearchOut(category=body.category, items=[match_out(m) for m in matches], note=note)


# --- kandydaci --------------------------------------------------------------------------------


@router.get(f"{W}/candidates", responses=_READ, summary="Lista kandydatów")
def list_candidates(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    state: str | None = Query(default="saved", pattern="^(saved|rejected)$"),
) -> list[CandidateOut]:
    return [
        CandidateOut.build(c, v.name, v.city)
        for c, v in service.list_candidates(db, principal, wedding_id, state)
    ]


@router.post(
    f"{W}/candidates", status_code=201, responses=_WRITE, summary="Zapisz firmę z katalogu"
)
def save_candidate(
    wedding_id: UUID, body: CandidateIn, principal: CurrentPrincipal, db: DbSession
) -> CandidateOut:
    cand = service.save_candidate(db, principal, wedding_id, body.catalog_vendor_id, body.note)
    from app.modules.catalog.models import CatalogVendor

    vendor = db.get_one(CatalogVendor, cand.catalog_vendor_id)
    return CandidateOut.build(cand, vendor.name, vendor.city)


@router.patch(
    f"{W}/candidates/{{candidate_id}}", responses=_WRITE, summary="Zapisz/odrzuć kandydata"
)
def patch_candidate(
    wedding_id: UUID,
    candidate_id: UUID,
    body: CandidatePatch,
    principal: CurrentPrincipal,
    db: DbSession,
) -> CandidateOut:
    from app.modules.catalog.models import CatalogVendor

    cand = service.set_candidate_state(
        db, principal, wedding_id, candidate_id, body.state or "saved", body.note
    )
    vendor = db.get_one(CatalogVendor, cand.catalog_vendor_id)
    return CandidateOut.build(cand, vendor.name, vendor.city)


@router.post(
    f"{W}/candidates/{{candidate_id}}/to-vendor",
    responses=_WRITE,
    summary="Dodaj do moich usługodawców",
)
def candidate_to_vendor(
    wedding_id: UUID, candidate_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> CandidateOut:
    from app.modules.catalog.models import CatalogVendor

    cand = service.candidate_to_vendor(db, principal, wedding_id, candidate_id)
    vendor = db.get_one(CatalogVendor, cand.catalog_vendor_id)
    return CandidateOut.build(cand, vendor.name, vendor.city)


@router.get(f"{W}/candidates-compare", responses=_READ, summary="Porównanie 2–4 firm z katalogu")
def compare(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    ids: Annotated[list[UUID], Query(min_length=2, max_length=4)],
) -> CandidateCompareOut:
    matches = service.compare(db, principal, wedding_id, ids)
    category = matches[0].card.vendor.category if matches else next(iter(CATEGORIES))
    return CandidateCompareOut(category=category, items=[match_out(m) for m in matches])


# --- prośba o research -----------------------------------------------------------------------


@router.post(
    f"{W}/discovery-requests",
    status_code=202,
    responses=_WRITE,
    summary="Poproś o odświeżenie źródeł",
)
def create_request(
    wedding_id: UUID, body: DiscoveryIn, principal: CurrentPrincipal, db: DbSession
) -> DiscoveryOut:
    return DiscoveryOut.model_validate(
        service.request_discovery(db, principal, wedding_id, body.category, body.region)
    )


@router.get(f"{W}/discovery-requests", responses=_READ, summary="Zlecenia researchu")
def list_requests(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[DiscoveryOut]:
    return [
        DiscoveryOut.model_validate(r) for r in service.list_requests(db, principal, wedding_id)
    ]


@router.get(f"{W}/discovery-requests/{{request_id}}", responses=_READ, summary="Stan zlecenia")
def get_request(
    wedding_id: UUID, request_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> DiscoveryOut:
    return DiscoveryOut.model_validate(service.get_request(db, principal, wedding_id, request_id))


# --- czat ------------------------------------------------------------------------------------


@router.get(f"{W}/concierge/conversations", responses=_READ, summary="Rozmowy z asystentem")
def list_conversations(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[ConversationOut]:
    return [ConversationOut.of(c) for c in chat.list_conversations(db, principal, wedding_id)]


@router.post(
    f"{W}/concierge/conversations", status_code=201, responses=_WRITE, summary="Nowa rozmowa"
)
def create_conversation(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> ConversationOut:
    return ConversationOut.of(chat.create_conversation(db, principal, wedding_id))


@router.get(
    f"{W}/concierge/conversations/{{conversation_id}}/messages",
    responses=_READ,
    summary="Wiadomości rozmowy",
)
def get_messages(
    wedding_id: UUID, conversation_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[MessageOut]:
    return [MessageOut.of(m) for m in chat.get_messages(db, principal, wedding_id, conversation_id)]


@router.post(
    f"{W}/concierge/conversations/{{conversation_id}}/messages",
    status_code=202,
    responses=_WRITE,
    summary="Napisz do asystenta (odpowiedź w tle)",
)
def post_message(
    wedding_id: UUID,
    conversation_id: UUID,
    body: MessageIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> PostedOut:
    user_msg, reply = chat.post_message(db, principal, wedding_id, conversation_id, body.text)
    return PostedOut(user_message=MessageOut.of(user_msg), reply=MessageOut.of(reply))


_ = PreconditionRequired
