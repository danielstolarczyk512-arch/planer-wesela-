"""Rozmowy z asystentem: zapis wiadomości, zadanie w tle, ponowna kontrola uprawnień."""

from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import NotFound, RateLimited, Unprocessable
from app.jobs.queue import enqueue
from app.modules.ai.providers import ProviderError, get_provider
from app.modules.concierge import agent
from app.modules.concierge.models import Conversation, Message
from app.modules.identity.models import User
from app.modules.identity.service import ACTIVE_STATUSES, Principal
from app.modules.workspace.permissions import Action, authorize

log = structlog.get_logger()

REPLY_JOB = "concierge_reply"
MAX_TEXT = 2000
HISTORY_TURNS = 8
STALE_AFTER = timedelta(minutes=15)
NOTICE_AI_OFF = "Asystent AI jest wyłączony."
NOTICE_AI_DOWN = "Asystent AI jest chwilowo niedostępny."


def create_conversation(db: Session, principal: Principal, wedding_id: UUID) -> Conversation:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    conv = Conversation(wedding_id=wedding_id, created_by=principal.user.id)
    db.add(conv)
    db.commit()
    return conv


def get_conversation(
    db: Session, principal: Principal, wedding_id: UUID, conversation_id: UUID, action: Action
) -> Conversation:
    authorize(db, principal.user.id, wedding_id, action)
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono rozmowy.", code="concierge.conversation_not_found")
    return conv


def list_conversations(db: Session, principal: Principal, wedding_id: UUID) -> list[Conversation]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.wedding_id == wedding_id)
            .order_by(Conversation.created_at.desc())
            .limit(20)
        )
    )


def _expire_stale(db: Session, conv: Conversation) -> None:
    """Odpowiedź, która utknęła (restart bez ponowienia), nie wisi w nieskończoność."""
    for m in db.scalars(
        select(Message).where(
            Message.conversation_id == conv.id,
            Message.state == "pending",
            Message.created_at < utcnow() - STALE_AFTER,
        )
    ):
        m.state, m.content = "failed", "Nie udało się przygotować odpowiedzi. Spróbuj ponownie."


def get_messages(
    db: Session, principal: Principal, wedding_id: UUID, conversation_id: UUID
) -> list[Message]:
    conv = get_conversation(db, principal, wedding_id, conversation_id, Action.READ)
    _expire_stale(db, conv)
    db.commit()
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at, Message.id)
            .limit(200)
        )
    )


def post_message(
    db: Session, principal: Principal, wedding_id: UUID, conversation_id: UUID, text: str
) -> tuple[Message, Message]:
    """Zapisuje wiadomość pary i pustą odpowiedź w toku; odpowiedź przygotuje worker."""
    conv = get_conversation(db, principal, wedding_id, conversation_id, Action.WRITE)
    text = text.strip()
    if not text or len(text) > MAX_TEXT:
        raise Unprocessable(
            f"Wiadomość musi mieć od 1 do {MAX_TEXT} znaków.", code="concierge.bad_message"
        )
    since = utcnow() - timedelta(days=1)
    used = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.wedding_id == wedding_id, Message.role == "user", Message.created_at > since)
    )
    if (used or 0) >= get_settings().concierge_max_messages_per_day:
        raise RateLimited(3600)
    user_msg = Message(
        conversation_id=conv.id,
        wedding_id=wedding_id,
        role="user",
        content=text,
        author_id=principal.user.id,
    )
    pending = Message(
        conversation_id=conv.id,
        wedding_id=wedding_id,
        role="assistant",
        content="",
        state="pending",
    )
    db.add_all([user_msg, pending])
    db.flush()
    if conv.title is None:
        conv.title = text[:80]
    # Do kolejki trafia tylko identyfikator odpowiedzi — treść i uprawnienia worker czyta z bazy.
    enqueue(db, REPLY_JOB, {"message_id": str(pending.id)}, max_attempts=2)
    db.commit()
    return user_msg, pending


def _history(db: Session, conv_id: UUID, before: Message) -> list[tuple[str, str]]:
    rows = db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conv_id,
            Message.state == "done",
            Message.created_at < before.created_at,
            Message.role.in_(("user", "assistant")),
        )
        .order_by(Message.created_at.desc())
        .limit(HISTORY_TURNS * 2)
    ).all()
    return [(m.role, m.content) for m in reversed(rows)]


def _principal_for(db: Session, message: Message, wedding_id: UUID) -> Principal | None:
    """Użytkownik, który zadał pytanie — jeśli nadal ma konto i prawo do zapisu w weselu."""
    asked = db.scalar(
        select(Message)
        .where(
            Message.conversation_id == message.conversation_id,
            Message.role == "user",
            Message.created_at <= message.created_at,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    user = db.get(User, asked.author_id) if asked is not None and asked.author_id else None
    if user is None or user.status not in ACTIVE_STATUSES:
        return None
    try:
        authorize(db, user.id, wedding_id, Action.WRITE)
    except Exception:
        return None
    # Kontekst zadania w tle: bez sesji HTTP (id sesji nie są potrzebne serwisom).
    return Principal(user=user, session_id=UUID(int=0), family_id=UUID(int=0))


def _finish(db: Session, message: Message, result: agent.AgentResult | None, text: str) -> None:
    message.state = "done" if result is not None else "failed"
    message.content = text
    if result is not None:
        message.actions, message.cards = result.actions, result.cards
    db.commit()


def run_reply(db: Session, payload: dict[str, Any]) -> None:
    """Zadanie workera: odpowiedź asystenta. Dostawca AI niedostępny → tryb bez AI."""
    message = db.get(Message, UUID(payload["message_id"]))
    if message is None or message.state != "pending":
        return
    wedding_id = message.wedding_id
    principal = _principal_for(db, message, wedding_id)
    if principal is None:
        _finish(db, message, None, "Nie masz już uprawnień do tej rozmowy.")
        return
    asked = db.scalar(
        select(Message)
        .where(
            Message.conversation_id == message.conversation_id,
            Message.role == "user",
            Message.created_at <= message.created_at,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    user_text = asked.content if asked is not None else ""
    state = agent.TurnState(db=db, principal=principal, wedding_id=wedding_id)
    settings = get_settings()
    provider = get_provider()
    reason = None
    if not settings.ai_enabled:
        reason = NOTICE_AI_OFF
    elif provider.external:
        reason = "Asystent AI nie działa z zewnętrznym dostawcą bez zgody i umowy powierzenia."
    result: agent.AgentResult | None = None
    if reason is None:
        try:
            result = agent.run_agent(
                state, provider, _history(db, message.conversation_id, message), user_text
            )
        except ProviderError as exc:
            log.warning("concierge_provider_error", error=str(exc)[:200])
            db.rollback()
            reason = NOTICE_AI_DOWN
    if result is None:
        state = agent.TurnState(db=db, principal=principal, wedding_id=wedding_id)
        result = agent.fallback(state, reason or NOTICE_AI_DOWN)
    _finish(db, message, result, result.message)
    log.info("concierge_reply", message_id=str(message.id), used_ai=result.used_ai)
