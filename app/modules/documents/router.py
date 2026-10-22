from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.core.schemas import PatchModel
from app.modules.documents import service
from app.modules.documents.models import Document, DocumentVersion

router = APIRouter(tags=["dokumenty"])

DocumentKind = Literal["offer", "contract", "invoice", "payment_proof", "other"]
Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola tylko do odczytu"},
    409: {"description": "Limit lub konflikt"},
    413: {"description": "Plik zbyt duży"},
    422: {"description": "Nieobsługiwany lub uszkodzony plik"},
}
W = "/weddings/{wedding_id}"


class VersionOut(BaseModel):
    id: UUID
    version_no: int
    original_filename: str
    mime_type: str
    size_bytes: int
    text_status: Literal["pending", "processing", "done", "failed"]
    text_error: str | None
    scan_status: Literal["not_scanned", "pending", "clean", "infected"] = Field(
        description="Skan antywirusowy: pobranie tylko dla clean / not_scanned (skaner wyłączony)"
    )
    page_count: int | None
    ocr_used: bool
    created_at: Any


class DocumentOut(BaseModel):
    id: UUID
    kind: DocumentKind
    title: str
    vendor_id: UUID | None
    current_version_id: UUID | None
    versions: list[VersionOut]
    version: int


class DocumentUpdate(PatchModel):
    NOT_NULL = ("title", "kind")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: DocumentKind | None = None
    vendor_id: UUID | None = None


class PageText(BaseModel):
    page: int
    text: str


class TextOut(BaseModel):
    text_status: str
    text_error: str | None
    ocr_used: bool
    page_count: int | None
    pages: list[PageText]
    note: str = "Tekst rozpoznany automatycznie może zawierać błędy, szczególnie ze skanów (OCR)."


def _version_out(v: DocumentVersion) -> VersionOut:
    return VersionOut(
        id=v.id,
        version_no=v.version_no,
        original_filename=v.original_filename,
        mime_type=v.mime_type,
        size_bytes=v.size_bytes,
        text_status=v.text_status,
        text_error=v.text_error,
        scan_status=v.scan_status,
        page_count=v.page_count,
        ocr_used=v.ocr_used,
        created_at=v.created_at,
    )


def _out(db: DbSession, docs: list[Document]) -> list[DocumentOut]:
    versions = service.versions_of(db, [d.id for d in docs])
    return [
        DocumentOut.model_validate(
            {
                "id": d.id,
                "kind": d.kind,
                "title": d.title,
                "vendor_id": d.vendor_id,
                "current_version_id": d.current_version_id,
                "version": d.version,
                "versions": [_version_out(v) for v in versions[d.id]],
            }
        )
        for d in docs
    ]


async def _read(file: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise service.PayloadTooLarge(
            f"Maksymalny rozmiar pliku to {get_settings().max_upload_mb} MB."
        )
    return data


@router.post(
    f"{W}/documents",
    status_code=202,
    responses=_WRITE,
    summary="Wgranie dokumentu (PDF, DOCX, JPG, PNG); tekst wyodrębniany w tle",
)
async def upload_document(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    file: Annotated[UploadFile, File(description="Plik do 20 MB")],
    kind: Annotated[DocumentKind, Form()] = "other",
    title: Annotated[str | None, Form(max_length=200)] = None,
    vendor_id: Annotated[UUID | None, Form()] = None,
) -> DocumentOut:
    data = await _read(file)
    # Logika jest synchroniczna (SQLAlchemy, zapis pliku): poza pętlą zdarzeń.
    document = await run_in_threadpool(
        lambda: service.upload(
            db,
            principal,
            wedding_id,
            data=data,
            filename=file.filename,
            kind=kind,
            title=title,
            vendor_id=vendor_id,
        )
    )
    return await run_in_threadpool(lambda: _out(db, [document])[0])


@router.get(f"{W}/documents", responses=_READ, summary="Dokumenty wesela")
def list_documents(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    kind: DocumentKind | None = None,
    vendor_id: UUID | None = None,
) -> list[DocumentOut]:
    return _out(
        db, service.list_documents(db, principal, wedding_id, kind=kind, vendor_id=vendor_id)
    )


class SearchHit(BaseModel):
    document_id: UUID
    version_id: UUID
    title: str
    kind: DocumentKind
    vendor_id: UUID | None
    page: int | None = Field(description="Strona z trafieniem (gdy tekst ma podział na strony)")
    snippet: str | None = Field(description="Fragment tekstu wokół trafienia")
    in_title: bool = Field(description="Trafienie w tytule lub nazwie pliku")


@router.get(
    f"{W}/documents/search",
    responses=_READ,
    summary="Szukaj w dokumentach: tytuł, nazwa pliku, odczytany tekst (bez polskich znaków)",
)
def search_documents(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    q: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[SearchHit]:
    return [
        SearchHit.model_validate(h) for h in service.search_documents(db, principal, wedding_id, q)
    ]


@router.get(f"{W}/documents/{{document_id}}", responses=_READ, summary="Dokument z wersjami")
def get_document(
    wedding_id: UUID,
    document_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    response: Response,
) -> DocumentOut:
    d = service.get_document(db, principal, wedding_id, document_id)
    response.headers["ETag"] = etag(d.version)
    return _out(db, [d])[0]


@router.patch(
    f"{W}/documents/{{document_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Zmiana tytułu, rodzaju lub usługodawcy (If-Match)",
)
def update_document(
    wedding_id: UUID,
    document_id: UUID,
    principal: CurrentPrincipal,
    body: DocumentUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> DocumentOut:
    d = service.update_document(
        db, principal, wedding_id, document_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(d.version)
    return _out(db, [d])[0]


@router.delete(
    f"{W}/documents/{{document_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie dokumentu i plików",
)
def delete_document(
    wedding_id: UUID, document_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_document(db, principal, wedding_id, document_id)


@router.post(
    f"{W}/documents/{{document_id}}/versions",
    status_code=202,
    responses=_WRITE,
    summary="Nowa wersja dokumentu",
)
async def add_version(
    wedding_id: UUID,
    document_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    file: Annotated[UploadFile, File(description="Plik do 20 MB")],
) -> DocumentOut:
    data = await _read(file)
    d = await run_in_threadpool(
        lambda: service.add_version(
            db, principal, wedding_id, document_id, data=data, filename=file.filename
        )
    )
    return await run_in_threadpool(lambda: _out(db, [d])[0])


@router.get(
    f"{W}/documents/{{document_id}}/versions/{{version_id}}/file",
    responses=_READ,
    response_class=Response,
    summary="Pobranie pliku (zawsze jako załącznik)",
)
def download(
    wedding_id: UUID,
    document_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
) -> Response:
    data, v = service.get_file(db, principal, wedding_id, document_id, version_id)
    return Response(
        content=data,
        media_type=v.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(v.original_filename)}",
            "Content-Security-Policy": "sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    f"{W}/documents/{{document_id}}/versions/{{version_id}}/text",
    responses=_READ,
    summary="Wyodrębniony tekst (podział na strony)",
)
def get_text(
    wedding_id: UUID,
    document_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
) -> TextOut:
    v = service.get_version(db, principal, wedding_id, document_id, version_id)
    return TextOut(
        text_status=v.text_status,
        text_error=v.text_error,
        ocr_used=v.ocr_used,
        page_count=v.page_count,
        pages=[PageText(page=i + 1, text=t) for i, t in enumerate(service.pages(v))],
    )


@router.post(
    f"{W}/documents/{{document_id}}/versions/{{version_id}}/retry",
    status_code=202,
    responses=_WRITE,
    summary="Ponowne wyodrębnienie tekstu",
)
def retry(
    wedding_id: UUID,
    document_id: UUID,
    version_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
) -> VersionOut:
    return _version_out(
        service.retry_extraction(db, principal, wedding_id, document_id, version_id)
    )
