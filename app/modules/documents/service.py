"""Dokumenty: upload z walidacją, wersje, ekstrakcja tekstu w workerze, pobieranie."""

import hashlib
from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import antivirus
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError, Conflict, NotFound, Unprocessable
from app.core.storage import get_storage, new_key, wedding_prefix
from app.jobs.queue import enqueue
from app.modules.audit import service as audit
from app.modules.documents import filetypes
from app.modules.documents.extraction import ExtractionError, extract
from app.modules.documents.models import DOWNLOADABLE, Document, DocumentVersion
from app.modules.identity.service import Principal
from app.modules.workspace.permissions import Action, authorize

log = structlog.get_logger()

EXTRACT_JOB = "extract_text"
SCAN_JOB = "scan_file"
# Skaner niedostępny: ponawiamy z rosnącą przerwą (do 1 h) przez ok. 2 doby; plik do tego czasu
# jest zablokowany (bez pobierania i ekstrakcji) — niczego nie przepuszczamy bez sprawdzenia.
SCAN_MAX_ATTEMPTS = 50
INFECTED_TEXT = "Plik zablokowany: skaner wykrył zagrożenie. Usuńcie go i poproście o nową kopię."
DELETE_PREFIX_JOB = "storage_delete_prefix"


class PayloadTooLarge(AppError):
    status, code, title = 413, "document.too_large", "Plik jest zbyt duży"


def _record(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    entity_id: UUID,
    action: str,
    changes: dict[str, Any] | None = None,
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="document",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
        changes=changes,
    )


def _document(db: Session, wedding_id: UUID, document_id: UUID) -> Document:
    d = db.get(Document, document_id)
    if d is None or d.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono dokumentu.", code="document.not_found")
    return d


def _version(db: Session, document: Document, version_id: UUID) -> DocumentVersion:
    v = db.get(DocumentVersion, version_id)
    if v is None or v.document_id != document.id:
        raise NotFound("Nie znaleziono wersji dokumentu.", code="document.version_not_found")
    return v


def versions_of(db: Session, document_ids: list[UUID]) -> dict[UUID, list[DocumentVersion]]:
    result: dict[UUID, list[DocumentVersion]] = {d: [] for d in document_ids}
    if document_ids:
        for v in db.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id.in_(document_ids))
            .order_by(DocumentVersion.version_no)
        ):
            result[v.document_id].append(v)
    return result


def _check_vendor(db: Session, wedding_id: UUID, vendor_id: UUID | None) -> None:
    if vendor_id is not None:
        from app.modules.vendors import service as vendors

        vendors.get_in_wedding(db, wedding_id, vendor_id)


def _check_quota(db: Session, wedding_id: UUID, new_bytes: int, new_document: bool) -> None:
    settings = get_settings()
    if new_bytes > settings.max_upload_mb * 1024 * 1024:
        raise PayloadTooLarge(f"Maksymalny rozmiar pliku to {settings.max_upload_mb} MB.")
    if new_document:
        count = (
            db.scalar(
                select(func.count()).select_from(Document).where(Document.wedding_id == wedding_id)
            )
            or 0
        )
        if count >= settings.max_documents_per_wedding:
            raise Conflict("Osiągnięto limit dokumentów dla wesela.", code="document.quota")
    used = (
        db.scalar(
            select(func.coalesce(func.sum(DocumentVersion.size_bytes), 0)).where(
                DocumentVersion.wedding_id == wedding_id
            )
        )
        or 0
    )
    if used + new_bytes > settings.max_storage_mb_per_wedding * 1024 * 1024:
        raise Conflict("Osiągnięto limit miejsca na pliki dla wesela.", code="document.quota")


def _add_version(
    db: Session, principal: Principal, document: Document, data: bytes, filename: str | None
) -> DocumentVersion:
    mime = filetypes.detect(data)
    sha = hashlib.sha256(data).hexdigest()
    same = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.wedding_id == document.wedding_id, DocumentVersion.sha256 == sha)
        .order_by(DocumentVersion.created_at)
    ).first()
    number = (
        db.scalar(
            select(func.max(DocumentVersion.version_no)).where(
                DocumentVersion.document_id == document.id
            )
        )
        or 0
    ) + 1
    version = DocumentVersion(
        document_id=document.id,
        wedding_id=document.wedding_id,
        version_no=number,
        sha256=sha,
        mime_type=mime,
        size_bytes=len(data),
        uploaded_by=principal.user.id,
        original_filename=filetypes.sanitize_filename(filename, mime),
        storage_key=same.storage_key if same else new_key(document.wedding_id),
    )
    if same is not None and same.scan_status == "infected":
        raise Unprocessable(
            "Ten plik został wcześniej zablokowany przez skaner antywirusowy.",
            code="document.infected",
        )
    if antivirus.enabled():
        # Ten sam plik już sprawdzony: wynik skanu bez ponownego skanowania.
        version.scan_status = (
            same.scan_status if same and same.scan_status == "clean" else "pending"
        )
    if same is not None and same.text_status == "done" and version.scan_status != "pending":
        # Ten sam plik już przetworzony w tym weselu: bez ponownego OCR.
        version.text_status, version.extracted_text = "done", same.extracted_text
        version.page_offsets, version.page_count = same.page_offsets, same.page_count
        version.ocr_used = same.ocr_used
    db.add(version)
    db.flush()
    if same is None:
        get_storage().put(version.storage_key, data)
    if version.scan_status == "pending":
        _enqueue_scan(db, version)
    elif version.text_status == "pending":
        enqueue(db, EXTRACT_JOB, {"version_id": str(version.id)}, wedding_id=document.wedding_id)
    document.current_version_id = version.id
    return version


def _enqueue_scan(db: Session, version: DocumentVersion) -> None:
    enqueue(
        db,
        SCAN_JOB,
        {"version_id": str(version.id)},
        wedding_id=version.wedding_id,
        max_attempts=SCAN_MAX_ATTEMPTS,
    )


def _ensure_downloadable(version: DocumentVersion) -> None:
    if version.scan_status == "pending":
        raise Conflict(
            "Plik jest jeszcze sprawdzany przez skaner antywirusowy. Spróbujcie za chwilę.",
            code="document.scan_pending",
        )
    if version.scan_status == "infected":
        raise Conflict(INFECTED_TEXT, code="document.infected")


def upload(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    data: bytes,
    filename: str | None,
    kind: str,
    title: str | None,
    vendor_id: UUID | None,
) -> Document:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _check_vendor(db, wedding_id, vendor_id)
    _check_quota(db, wedding_id, len(data), new_document=True)
    mime = filetypes.detect(data)
    document = Document(
        wedding_id=wedding_id,
        kind=kind,
        vendor_id=vendor_id,
        title=(title or filetypes.sanitize_filename(filename, mime))[:200],
    )
    db.add(document)
    db.flush()
    version = _add_version(db, principal, document, data, filename)
    _record(
        db,
        principal,
        wedding_id,
        document.id,
        "upload",
        {
            "version": [None, version.version_no],
            "mime": [None, version.mime_type],
            "size": [None, version.size_bytes],
        },
    )
    db.commit()
    return document


def add_version(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    document_id: UUID,
    *,
    data: bytes,
    filename: str | None,
) -> Document:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    document = _document(db, wedding_id, document_id)
    _check_quota(db, wedding_id, len(data), new_document=False)
    version = _add_version(db, principal, document, data, filename)
    _record(
        db,
        principal,
        wedding_id,
        document.id,
        "new_version",
        {"version": [None, version.version_no]},
    )
    db.commit()
    return document


def list_documents(
    db: Session, principal: Principal, wedding_id: UUID, *, kind: str | None, vendor_id: UUID | None
) -> list[Document]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    stmt = select(Document).where(Document.wedding_id == wedding_id)
    if kind:
        stmt = stmt.where(Document.kind == kind)
    if vendor_id:
        stmt = stmt.where(Document.vendor_id == vendor_id)
    return list(db.scalars(stmt.order_by(Document.created_at.desc())))


# --- wyszukiwanie w treści ----------------------------------------------------------------

_PL_FROM = "ąćęłńóśźż"
_PL_TO = "acelnoszz"
_FOLD = str.maketrans(_PL_FROM, _PL_TO)
SEARCH_LIMIT = 50
SNIPPET_RADIUS = 80


def fold(text: str) -> str:
    """Małe litery bez polskich znaków (ta sama zamiana co w SQL: lower + translate)."""
    return text.lower().translate(_FOLD)


def _snippet(text: str, terms: list[str]) -> tuple[str, int] | None:
    """Fragment wokół pierwszego trafienia któregoś słowa i jego pozycja (porównanie po `fold`)."""
    folded = fold(text)
    found = [(p, t) for t in terms if (p := folded.find(t)) >= 0]
    if not found:
        return None
    pos, term = min(found)
    start, end = max(0, pos - SNIPPET_RADIUS), min(len(text), pos + len(term) + SNIPPET_RADIUS)
    snippet = " ".join(text[start:end].split())
    return ("…" if start else "") + snippet + ("…" if end < len(text) else ""), pos


# Typowe końcówki odmiany (po `fold`), najdłuższe najpierw. Prosty stemming bez słownika:
# „sali” → „sal” (znajdzie „sala”, „salą”), „umowie” → „umow”, „złotej” → „zlot”.
_ENDINGS = (
    "iami", "ami", "ach", "ego", "emu", "ich", "ych", "imi", "ymi", "iem",
    "em", "om", "ow", "ej", "ie", "ia", "ii", "im", "ym",
)  # fmt: skip
_VOWELS = ("a", "e", "i", "o", "u", "y")
SEARCH_TERMS = 6


def stem(word: str) -> str:
    """Rdzeń słowa do wyszukiwania (odcięta końcówka, zostają co najmniej 3 znaki)."""
    if len(word) < 4:
        return word
    for ending in (*_ENDINGS, *_VOWELS):
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: -len(ending)]
    return word


def search_terms(query: str) -> list[str]:
    """Słowa zapytania po `fold` i stemmingu (bez jednoliterowych, najwyżej 6)."""
    return [stem(w) for w in fold(query).split() if len(w) >= 2][:SEARCH_TERMS]


def search_documents(
    db: Session, principal: Principal, wedding_id: UUID, query: str
) -> list[dict[str, Any]]:
    """Szuka w tytule, nazwie pliku i odczytanym tekście bieżących wersji dokumentów.

    Bez rozróżniania wielkości liter i polskich znaków, z prostą odmianą słów („sali” znajdzie
    „sala”, „zaliczki” — „zaliczkę”); każde słowo zapytania musi wystąpić (w dowolnym miejscu).
    Bez rozszerzeń PostgreSQL: `lower()` + `translate()`.
    Zainfekowane i niesprawdzone pliki nie mają tekstu, więc nie trafiają do wyników treści.
    """
    authorize(db, principal.user.id, wedding_id, Action.READ)
    terms = search_terms(query)
    if not terms:
        return []

    def folded(col: Any) -> Any:
        return func.translate(func.lower(col), _PL_FROM, _PL_TO)

    def matches(term: str) -> Any:
        pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return (
            folded(Document.title).like(pattern, escape="\\")
            | folded(DocumentVersion.original_filename).like(pattern, escape="\\")
            | folded(func.coalesce(DocumentVersion.extracted_text, "")).like(pattern, escape="\\")
        )

    rows = db.execute(
        select(Document, DocumentVersion)
        .join(DocumentVersion, DocumentVersion.id == Document.current_version_id)
        .where(Document.wedding_id == wedding_id, *[matches(t) for t in terms])
        .order_by(Document.created_at.desc())
        .limit(SEARCH_LIMIT)
    ).all()
    results = []
    for doc, version in rows:
        hit = _snippet(version.extracted_text or "", terms)
        page = None
        if hit and version.page_offsets:
            page = next(
                (
                    n
                    for n, (start, end) in enumerate(version.page_offsets, 1)
                    if start <= hit[1] < end
                ),
                None,
            )
        results.append(
            {
                "document_id": doc.id,
                "version_id": version.id,
                "title": doc.title,
                "kind": doc.kind,
                "vendor_id": doc.vendor_id,
                "page": page,
                "snippet": hit[0] if hit else None,
                "in_title": all(t in fold(doc.title) for t in terms)
                or all(t in fold(version.original_filename) for t in terms),
            }
        )
    return results


def get_document(
    db: Session, principal: Principal, wedding_id: UUID, document_id: UUID
) -> Document:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _document(db, wedding_id, document_id)


def update_document(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    document_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Document:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    document = _document(db, wedding_id, document_id)
    if document.version != version:
        raise Conflict("Dokument zmienił się w międzyczasie.", code="conflict.version_mismatch")
    if "vendor_id" in data:
        _check_vendor(db, wedding_id, data["vendor_id"])
    before = {k: getattr(document, k) for k in data}
    for k, v in data.items():
        if v is not None or k == "vendor_id":
            setattr(document, k, v)
    _record(db, principal, wedding_id, document.id, "update", audit.diff(before, data))
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Dokument zmienił się w międzyczasie.", code="conflict.version_mismatch"
        ) from exc
    return document


def _keys_still_used(db: Session, keys: set[str], exclude_document: UUID) -> set[str]:
    if not keys:
        return set()
    return set(
        db.scalars(
            select(DocumentVersion.storage_key).where(
                DocumentVersion.storage_key.in_(keys),
                DocumentVersion.document_id != exclude_document,
            )
        )
    )


def delete_document(db: Session, principal: Principal, wedding_id: UUID, document_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    document = _document(db, wedding_id, document_id)
    keys = {v.storage_key for v in versions_of(db, [document.id])[document.id]}
    orphaned = keys - _keys_still_used(db, keys, document.id)
    db.delete(document)
    _record(db, principal, wedding_id, document_id, "delete")
    db.commit()
    storage = get_storage()
    for key in orphaned:
        storage.delete(key)


def get_file(
    db: Session, principal: Principal, wedding_id: UUID, document_id: UUID, version_id: UUID
) -> tuple[bytes, DocumentVersion]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    version = _version(db, _document(db, wedding_id, document_id), version_id)
    _ensure_downloadable(version)
    return get_storage().get(version.storage_key), version


def get_version(
    db: Session, principal: Principal, wedding_id: UUID, document_id: UUID, version_id: UUID
) -> DocumentVersion:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _version(db, _document(db, wedding_id, document_id), version_id)


def version_in_wedding(db: Session, wedding_id: UUID, version_id: UUID) -> DocumentVersion:
    """Dla modułu ofert: wersja dokumentu musi należeć do tego wesela."""
    v = db.get(DocumentVersion, version_id)
    if v is None or v.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono wersji dokumentu.", code="document.version_not_found")
    return v


def pages(version: DocumentVersion) -> list[str]:
    text = version.extracted_text or ""
    return [text[start:end] for start, end in (version.page_offsets or [])]


def retry_extraction(
    db: Session, principal: Principal, wedding_id: UUID, document_id: UUID, version_id: UUID
) -> DocumentVersion:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    version = _version(db, _document(db, wedding_id, document_id), version_id)
    if version.text_status in ("pending", "processing"):
        raise Conflict("Przetwarzanie już trwa.", code="document.extraction_in_progress")
    _ensure_downloadable(version)
    version.text_status, version.text_error = "pending", None
    enqueue(db, EXTRACT_JOB, {"version_id": str(version.id)}, wedding_id=wedding_id)
    db.commit()
    return version


# --- zadania workera -------------------------------------------------------------------


def run_scan(db: Session, payload: dict[str, Any]) -> None:
    """Skan pliku. Brak skanera = wyjątek → kolejka ponawia (plik pozostaje zablokowany)."""
    version = db.get(DocumentVersion, UUID(payload["version_id"]))
    if version is None or version.scan_status != "pending":
        return  # usunięty albo już sprawdzony (np. ten sam plik w innej wersji)
    result = antivirus.scan(get_storage().get(version.storage_key))
    # Wersje z tym samym plikiem (ten sam storage_key) dzielą wynik.
    same_file = list(
        db.scalars(
            select(DocumentVersion).where(
                DocumentVersion.storage_key == version.storage_key,
                DocumentVersion.scan_status == "pending",
            )
        )
    )
    if result.clean:
        for v in same_file:
            v.scan_status = "clean"
            if v.text_status == "pending":
                enqueue(db, EXTRACT_JOB, {"version_id": str(v.id)}, wedding_id=v.wedding_id)
        db.commit()
        return
    for v in same_file:
        v.scan_status, v.scan_signature = "infected", result.signature
        v.text_status, v.text_error = "failed", INFECTED_TEXT
        audit.record(
            db,
            actor_type="system",
            actor_id=None,
            entity_type="document_version",
            entity_id=v.id,
            wedding_id=v.wedding_id,
            action="infected",
            changes={"signature": [None, result.signature]},
        )
    db.commit()
    # Kwarantanna: plik znika z magazynu (nie da się go pobrać ani przetworzyć).
    get_storage().delete(version.storage_key)
    log.warning("document_infected", version_id=str(version.id), signature=result.signature)


def queue_unscanned(db: Session, limit: int = 100) -> int:
    """Gdy skaner działa: pliki sprzed jego wdrożenia (not_scanned) idą do sprawdzenia."""
    if not antivirus.enabled():
        return 0
    versions = list(
        db.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.scan_status == "not_scanned")
            .order_by(DocumentVersion.created_at)
            .limit(limit)
        )
    )
    for v in versions:
        v.scan_status = "pending"
        _enqueue_scan(db, v)
    db.commit()
    return len(versions)


def run_extraction(db: Session, payload: dict[str, Any]) -> None:
    version = db.get(DocumentVersion, UUID(payload["version_id"]))
    if version is None:  # dokument usunięty przed przetworzeniem
        return
    if version.scan_status not in DOWNLOADABLE:
        return  # niesprawdzony albo zainfekowany: bez ekstrakcji (wróci po czystym skanie)
    version.text_status = "processing"
    db.commit()
    try:
        result = extract(get_storage().get(version.storage_key), version.mime_type)
    except ExtractionError as exc:
        version.text_status, version.text_error = "failed", str(exc)[:300]
    except Exception as exc:  # nieprzewidziany błąd biblioteki: nie ponawiamy w kółko
        log.exception(
            "extraction_failed", version_id=str(version.id), error_type=type(exc).__name__
        )
        version.text_status = "failed"
        version.text_error = "Nie udało się przetworzyć pliku. Spróbuj ponownie lub wpisz dane."
    else:
        version.text_status = "done"
        version.extracted_text = result.text
        version.page_offsets = result.page_offsets
        version.page_count = result.page_count
        version.ocr_used = result.ocr_used
        version.text_error = None
    db.commit()


def run_delete_prefix(_db: Session, payload: dict[str, Any]) -> None:
    get_storage().delete_prefix(payload["prefix"])


ORPHAN_GRACE = timedelta(hours=24)
ORPHAN_BATCH = 500


def purge_orphan_files(db: Session) -> int:
    """Usuwa pliki bez rekordu wersji (np. zapis pliku, a potem awaria bazy przed commit).

    Pliki młodsze niż doba zostają: mogą należeć do trwającego właśnie uploadu.
    Klucze sprawdzane partiami (bez ładowania wszystkich kluczy do pamięci).
    """
    storage = get_storage()
    cutoff = utcnow() - ORPHAN_GRACE
    removed = 0

    def flush(batch: list[str]) -> int:
        known = set(
            db.scalars(
                select(DocumentVersion.storage_key).where(DocumentVersion.storage_key.in_(batch))
            )
        )
        orphans = [k for k in batch if k not in known]
        for key in orphans:
            storage.delete(key)
        return len(orphans)

    batch: list[str] = []
    for key, modified in storage.list_keys("weddings"):
        if modified < cutoff:
            batch.append(key)
        if len(batch) >= ORPHAN_BATCH:
            removed += flush(batch)
            batch = []
    if batch:
        removed += flush(batch)
    if removed:
        log.info("orphan_files_purged", count=removed)
    return removed


def on_wedding_deleted(db: Session, wedding_id: UUID) -> None:
    """Wywoływane przy usunięciu wesela: pliki usuwa worker (po commit transakcji)."""
    enqueue(db, DELETE_PREFIX_JOB, {"prefix": wedding_prefix(wedding_id)})


def ensure_text(text_status: str) -> None:
    if text_status != "done":
        raise Unprocessable(
            "Tekst dokumentu nie jest jeszcze gotowy.", code="document.text_not_ready"
        )
