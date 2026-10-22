"""Etap 6: retencja dziennika audytu i sprzątanie osieroconych plików."""

import os
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.modules.audit import service as audit
from app.modules.audit.models import AuditLog, SecurityEvent
from app.modules.documents import service as documents
from tests.api.test_documents import drain_jobs, pdf_sample, upload


def _audit(db, action, age):
    db.add(
        AuditLog(
            occurred_at=utcnow() - age,
            actor_type="system",
            entity_type="test",
            entity_id="x",
            action=action,
        )
    )


def test_audit_retention_only_old_rows_and_only_via_procedure():
    with get_sessionmaker()() as db:
        _audit(db, "stary", timedelta(days=760))
        _audit(db, "swiezy", timedelta(days=30))
        db.add(SecurityEvent(type="login_failed", occurred_at=utcnow() - timedelta(days=400)))
        db.add(SecurityEvent(type="login_failed", occurred_at=utcnow() - timedelta(days=10)))
        db.commit()

        # Zwykły DELETE i UPDATE są nadal blokowane przez bazę.
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM audit_log WHERE action = 'stary'"))
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(update(AuditLog).values(action="zmiana"))
        db.rollback()
        # Nawet z flagą retencji nie da się usunąć świeżego wpisu.
        db.execute(text("SET LOCAL wp.audit_retention = 'on'"))
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM audit_log WHERE action = 'swiezy'"))
        db.rollback()

        stats = audit.purge_expired(db)
        assert stats == {"audit_log_purged": 1, "security_events_purged": 1}
        assert set(db.scalars(select(AuditLog.action))) == {"swiezy"}
        # Flaga obowiązywała tylko w transakcji procedury.
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM audit_log"))
        db.rollback()


def test_orphan_files_purged_after_grace(client, alice, wedding):
    upload(client, alice, wedding, pdf_sample())
    drain_jobs()
    root = Path(get_settings().storage_dir)
    old_orphan = root / "weddings" / wedding["id"] / "osierocony-stary"
    new_orphan = root / "weddings" / wedding["id"] / "osierocony-nowy"
    for p in (old_orphan, new_orphan):
        p.write_bytes(b"x")
    two_days_ago = (utcnow() - timedelta(days=2)).timestamp()
    os.utime(old_orphan, (two_days_ago, two_days_ago))
    kept = [p for p in (root / "weddings" / wedding["id"]).iterdir() if "osierocony" not in p.name]

    with get_sessionmaker()() as db:
        assert documents.purge_orphan_files(db) == 1
    assert not old_orphan.exists()
    assert new_orphan.exists()  # może należeć do trwającego uploadu
    assert all(p.exists() for p in kept)
    assert kept  # plik dokumentu z bazą zostaje


def test_orphan_files_checked_in_batches(client, alice, wedding, monkeypatch):
    upload(client, alice, wedding, pdf_sample())
    drain_jobs()
    root = Path(get_settings().storage_dir) / "weddings" / wedding["id"]
    orphans = [root / f"osierocony-{n}" for n in range(3)]
    for p in orphans:
        p.write_bytes(b"x")
    old = (utcnow() - timedelta(days=2)).timestamp()
    files = [p for p in root.rglob("*") if p.is_file()]
    for p in files:  # także plik dokumentu: musi go uratować rekord w bazie, nie wiek
        os.utime(p, (old, old))
    monkeypatch.setattr(documents, "ORPHAN_BATCH", 1)

    with get_sessionmaker()() as db:
        assert documents.purge_orphan_files(db) == 3
    assert not any(p.exists() for p in orphans)
    assert [p for p in root.rglob("*") if p.is_file()]  # plik dokumentu został
