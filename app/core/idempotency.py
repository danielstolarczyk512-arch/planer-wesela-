"""Idempotency-Key dla POST: ponowienie żądania (np. słaby zasięg) zwraca zapisaną odpowiedź.

Klucz jest powiązany z użytkownikiem (sub z access tokena) i treścią żądania. Odpowiedzi
trzymamy 24 h. Nie zapisujemy odpowiedzi zawierających sekrety (linki RSVP, logowanie).

Odtworzenie zapisanej odpowiedzi to też odczyt danych, więc przed nim sprawdzamy to samo co
endpoint: aktywną sesję (wylogowanie, odwołanie) oraz — dla ścieżek wesela — że użytkownik
nadal jest członkiem z tą samą rolą co przy pierwszym żądaniu.
"""

import hashlib
import json
import re
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from anyio import to_thread
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    delete,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.db import Base, get_sessionmaker, utcnow
from app.core.errors import AppError
from app.core.security import decode_access_token

KEY_RE = re.compile(r"^[A-Za-z0-9_\-:.]{8,128}$")
WEDDING_PATH_RE = re.compile(r"/weddings/([0-9a-fA-F-]{36})(?:/|$)")
EXCLUDED = ("/auth/", "/rsvp-link", "/rsvp/")
MAX_STORED_BODY = 1_000_000
TTL = timedelta(hours=24)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(128))
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(300))
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(100))
    # Rola w weselu ze ścieżki w chwili pierwszego żądania; inna przy ponowieniu → bez odtworzenia.
    member_role: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),)


def purge_expired(db: Session) -> int:
    result = db.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < utcnow() - TTL))
    return int(getattr(result, "rowcount", 0) or 0)


def _problem(status: int, code: str, detail: str) -> tuple[int, bytes]:
    body = {
        "type": "about:blank",
        "title": detail,
        "status": status,
        "detail": detail,
        "code": code,
    }
    return status, json.dumps(body, ensure_ascii=False).encode()


def _wedding_id(path: str) -> UUID | None:
    match = WEDDING_PATH_RE.search(path)
    if match is None:
        return None
    with suppress(ValueError):
        return UUID(match.group(1))
    return None


def _member_role(db: Session, user_id: UUID, wedding_id: UUID | None) -> str | None:
    from app.modules.workspace.models import WeddingMember  # core nie zależy od modułów

    if wedding_id is None:
        return None
    member = db.get(WeddingMember, (wedding_id, user_id))
    return member.role if member is not None else None


def _app_error(exc: AppError) -> tuple[int, bytes]:
    return _problem(exc.status, exc.code, exc.detail)


def _claim(
    user_id: UUID, session_id: UUID, key: str, method: str, path: str, request_hash: str
) -> tuple[str, Any]:
    """Zwraca ("new", id) | ("replay", (status, body, ctype)) | ("error", (status, body))."""
    from app.modules.identity.service import authenticate  # core nie zależy od modułów

    with get_sessionmaker()() as db:
        try:
            authenticate(db, user_id, session_id)
        except AppError as exc:
            return "error", _app_error(exc)
        wedding_id = _wedding_id(path)
        role = _member_role(db, user_id, wedding_id)
        existing = db.scalars(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id, IdempotencyKey.key == key
            )
        ).first()
        if existing is not None and existing.created_at < utcnow() - TTL:
            db.delete(existing)
            db.commit()
            existing = None
        if existing is not None:
            if existing.request_hash != request_hash:
                return "error", _problem(
                    422,
                    "idempotency.key_reused",
                    "Ten Idempotency-Key użyto już dla innego żądania.",
                )
            if existing.status_code is None:
                return "error", _problem(
                    409,
                    "idempotency.in_progress",
                    "Żądanie z tym kluczem jest w trakcie obsługi.",
                )
            if wedding_id is not None and role is None:
                return "error", _problem(404, "wedding.not_found", "Nie znaleziono wesela.")
            if role != existing.member_role:
                return "error", _problem(
                    403,
                    "idempotency.context_changed",
                    "Twoja rola w weselu zmieniła się. Odśwież stronę i spróbuj ponownie.",
                )
            return "replay", (
                existing.status_code,
                (existing.response_body or "").encode(),
                existing.content_type or "application/json",
            )
        record = IdempotencyKey(
            user_id=user_id,
            key=key,
            method=method,
            path=path[:300],
            request_hash=request_hash,
            member_role=role,
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return "error", _problem(
                409, "idempotency.in_progress", "Żądanie z tym kluczem jest w trakcie obsługi."
            )
        return "new", record.id


def _finish(record_id: int, status: int, body: bytes, content_type: str) -> None:
    with get_sessionmaker()() as db:
        record = db.get(IdempotencyKey, record_id)
        if record is None:
            return
        if status >= 500 or len(body) > MAX_STORED_BODY:
            db.delete(record)  # błąd serwera: klient może bezpiecznie ponowić
        else:
            record.status_code = status
            record.response_body = body.decode("utf-8", errors="replace")
            record.content_type = content_type[:100]
        db.commit()


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        raw_key = headers.get(b"idempotency-key")
        path: str = scope["path"]
        if raw_key is None or any(part in path for part in EXCLUDED):
            await self.app(scope, receive, send)
            return
        key = raw_key.decode("latin-1")
        if not KEY_RE.match(key):
            await _respond(
                send,
                *_problem(
                    422,
                    "idempotency.invalid_key",
                    "Idempotency-Key: 8-128 znaków [A-Za-z0-9_-:.].",
                ),
            )
            return
        identity = _identity_from(headers)
        if identity is None:  # brak/nieprawidłowy token: endpoint sam zwróci 401
            await self.app(scope, receive, send)
            return
        user_id, session_id = identity

        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        request_hash = hashlib.sha256(
            scope["method"].encode() + path.encode() + b"\n" + body
        ).hexdigest()
        outcome, value = await to_thread.run_sync(
            _claim, user_id, session_id, key, scope["method"], path, request_hash
        )
        if outcome == "error":
            await _respond(send, *value)
            return
        if outcome == "replay":
            status, stored, ctype = value
            await _respond(send, status, stored, ctype, replayed=True)
            return

        sent_body = False

        async def replay_receive() -> Message:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        captured: dict[str, Any] = {"status": 500, "headers": [], "body": b""}

        async def capture_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                captured["body"] += message.get("body", b"")
            await send(message)

        try:
            await self.app(scope, replay_receive, capture_send)
        finally:
            ctype = dict(captured["headers"]).get(b"content-type", b"application/json")
            await to_thread.run_sync(
                _finish, value, captured["status"], captured["body"], ctype.decode("latin-1")
            )


def _identity_from(headers: dict[bytes, bytes]) -> tuple[UUID, UUID] | None:
    """(użytkownik, sesja) z access tokena; ważność sesji sprawdza `_claim`."""
    auth = headers.get(b"authorization", b"").decode("latin-1")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        return decode_access_token(auth[7:].strip())
    except AppError:
        return None


async def _respond(
    send: Send,
    status: int,
    body: bytes,
    content_type: str = "application/problem+json",
    replayed: bool = False,
) -> None:
    headers = [
        (b"content-type", content_type.encode()),
        (b"content-length", str(len(body)).encode()),
    ]
    if replayed:
        headers.append((b"idempotency-replayed", b"true"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
