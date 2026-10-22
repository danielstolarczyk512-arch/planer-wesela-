from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete, func, text
from sqlalchemy.orm import Session

from app.core.context import request_id_var
from app.core.db import utcnow
from app.modules.audit.models import AuditLog, SecurityEvent

log = structlog.get_logger()


def record(
    db: Session,
    *,
    actor_type: str,
    actor_id: UUID | None,
    entity_type: str,
    entity_id: UUID | str | None,
    action: str,
    wedding_id: UUID | None = None,
    changes: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            wedding_id=wedding_id,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            action=action,
            changes=changes,
            request_id=request_id_var.get(),
        )
    )


def security_event(
    db: Session,
    event_type: str,
    *,
    user_id: UUID | None = None,
    ip_prefix: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(SecurityEvent(type=event_type, user_id=user_id, ip_prefix=ip_prefix, details=details))
    log.info("security_event", type=event_type, user_id=str(user_id) if user_id else None)


SECURITY_EVENTS_RETENTION = timedelta(days=365)


def purge_expired(db: Session) -> dict[str, int]:
    """Retencja: dziennik audytu 24 mies., zdarzenia bezpieczeństwa 12 mies.

    Wyzwalacz w bazie przepuszcza DELETE z `audit_log` tylko w transakcji z ustawionym
    `wp.audit_retention` i tylko dla wpisów starszych niż 24 miesiące (zob. migracja a9052588a747).
    """
    db.execute(text("SET LOCAL wp.audit_retention = 'on'"))
    audit_rows = db.execute(
        delete(AuditLog).where(AuditLog.occurred_at < func.now() - text("interval '24 months'"))
    )
    security_rows = db.execute(
        delete(SecurityEvent).where(
            SecurityEvent.occurred_at < utcnow() - SECURITY_EVENTS_RETENTION
        )
    )
    db.commit()  # koniec transakcji kończy też SET LOCAL
    return {
        "audit_log_purged": int(getattr(audit_rows, "rowcount", 0) or 0),
        "security_events_purged": int(getattr(security_rows, "rowcount", 0) or 0),
    }


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Zmienione pola w formacie {pole: [stare, nowe]} (wartości jako str dla JSON)."""
    out: dict[str, Any] = {}
    for key, new in after.items():
        old = before.get(key)
        if old != new:
            out[key] = [_jsonable(old), _jsonable(new)]
    return out


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, bool | int | str):
        return v
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return str(v)
