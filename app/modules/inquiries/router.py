from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import CurrentPrincipal, DbSession
from app.modules.ai.router import AiRunOut, run_out
from app.modules.inquiries import schemas, service

router = APIRouter(tags=["zapytania do firm"])
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


@router.get(f"{W}/inquiries", responses=_READ, summary="Zapytania do firm")
def list_inquiries(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[schemas.InquiryOut]:
    return [
        schemas.build(db, principal, i) for i in service.list_inquiries(db, principal, wedding_id)
    ]


@router.post(
    f"{W}/inquiries", status_code=201, responses=_WRITE, summary="Szkice zapytań (nic nie wysyła)"
)
def create_drafts(
    wedding_id: UUID, body: schemas.DraftsIn, principal: CurrentPrincipal, db: DbSession
) -> list[schemas.InquiryOut]:
    created = service.create_drafts(
        db,
        principal,
        wedding_id,
        [r.model_dump() for r in body.recipients],
        tuple(q.strip() for q in body.extra_questions if q.strip()),
    )
    return [schemas.build(db, principal, i) for i in created]


@router.get(f"{W}/inquiries/{{inquiry_id}}", responses=_READ, summary="Zapytanie z odpowiedziami")
def get_inquiry(
    wedding_id: UUID, inquiry_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> schemas.InquiryOut:
    return schemas.build(db, principal, service.get_inquiry(db, principal, wedding_id, inquiry_id))


@router.put(
    f"{W}/inquiries/{{inquiry_id}}",
    responses=_WRITE,
    summary="Zmiana treści/adresata = nowa rewizja bez zgody",
)
def edit_inquiry(
    wedding_id: UUID,
    inquiry_id: UUID,
    body: schemas.EditIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> schemas.InquiryOut:
    service.edit(
        db,
        principal,
        wedding_id,
        inquiry_id,
        base_revision=body.base_revision,
        to_email=str(body.to_email),
        subject=body.subject,
        body=body.body,
    )
    return schemas.build(db, principal, service.get_inquiry(db, principal, wedding_id, inquiry_id))


@router.delete(
    f"{W}/inquiries/{{inquiry_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usuń szkic (niewysłany)",
)
def delete_inquiry(
    wedding_id: UUID, inquiry_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_draft(db, principal, wedding_id, inquiry_id)


def _approve(
    db: DbSession,
    principal: CurrentPrincipal,
    wedding_id: UUID,
    inquiry_id: UUID,
    body: schemas.ApproveIn,
) -> schemas.ApproveResult:
    _rev, _delivery, created = service.approve_and_send(
        db,
        principal,
        wedding_id,
        inquiry_id,
        revision_id=body.revision_id,
        content_hash=body.content_hash,
        to_email=str(body.to_email),
        acknowledge_warnings=body.acknowledge_warnings,
    )
    out = schemas.build(db, principal, service.get_inquiry(db, principal, wedding_id, inquiry_id))
    return schemas.ApproveResult(inquiry_id=inquiry_id, created=created, inquiry=out)


@router.post(
    f"{W}/inquiries/{{inquiry_id}}/approve-and-send",
    status_code=202,
    responses=_WRITE,
    summary="Zatwierdź rewizję i wyślij (idempotentne)",
)
def approve_and_send(
    wedding_id: UUID,
    inquiry_id: UUID,
    body: schemas.ApproveIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> schemas.ApproveResult:
    return _approve(db, principal, wedding_id, inquiry_id, body)


@router.post(
    f"{W}/inquiries-approve-and-send",
    status_code=202,
    responses=_WRITE,
    summary="Zatwierdź i wyślij kilka zapytań naraz",
)
def approve_batch(
    wedding_id: UUID, body: schemas.BatchApproveIn, principal: CurrentPrincipal, db: DbSession
) -> list[schemas.ApproveResult]:
    # Każde zapytanie ma własną zgodę i własną transakcję; błąd jednego nie cofa pozostałych.
    return [
        _approve(db, principal, wedding_id, inquiry_id, item) for inquiry_id, item in body.items
    ]


@router.post(
    f"{W}/inquiries/{{inquiry_id}}/import-response",
    status_code=201,
    responses=_WRITE,
    summary="Dodaj odpowiedź firmy (wklejona ręcznie)",
)
def import_response(
    wedding_id: UUID,
    inquiry_id: UUID,
    body: schemas.ResponseIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> schemas.ResponseOut:
    return schemas._resp(
        service.import_response(
            db,
            principal,
            wedding_id,
            inquiry_id,
            text=body.text,
            subject=body.subject,
            received_at=body.received_at,
        )
    )


@router.post(
    f"{W}/inquiries/{{inquiry_id}}/responses/{{response_id}}/analyze",
    status_code=202,
    responses=_WRITE,
    summary="Przeanalizuj odpowiedź (szkic oferty do zatwierdzenia)",
)
def analyze_response(
    wedding_id: UUID,
    inquiry_id: UUID,
    response_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
) -> AiRunOut:
    run = service.analyze_response(db, principal, wedding_id, inquiry_id, response_id)
    return run_out(run)
