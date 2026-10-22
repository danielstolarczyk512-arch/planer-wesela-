"""Skanowanie antywirusowe wgranych plików (ClamAV jako osobna usługa).

Przepływ przez prawdziwą kolejkę i worker; skaner zastąpiony dublerem (wynik/brak połączenia).
Test z prawdziwym clamd (plik EICAR) — tylko gdy WP_TEST_CLAMAV_HOST wskazuje działający skaner.
"""

import os

import pytest
from sqlalchemy import select

from app.core import antivirus
from app.core.config import get_settings
from app.jobs.queue import Job
from app.modules.documents.models import DocumentVersion
from tests.api.test_documents import API, drain_jobs, pdf_sample, storage_files, upload

# Standardowy plik testowy EICAR składany w czasie działania — dosłowny ciąg w źródle bywa
# blokowany przez antywirus stacji roboczej (Windows Defender).
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$" + b"EICAR-STANDARD-ANTIVIRUS-TEST-" + b"FILE!$H+H*"


@pytest.fixture
def scanner(monkeypatch):
    """Włączony skaner z wynikiem ustawianym w teście: 'clean', 'infected' albo 'down'."""
    state = {"result": "clean", "calls": 0}
    monkeypatch.setattr(get_settings(), "clamav_host", "clamav-test")

    def fake_scan(data: bytes) -> antivirus.ScanResult:
        state["calls"] += 1
        if state["result"] == "down":
            raise antivirus.ScannerUnavailable("ConnectionRefusedError")
        if state["result"] == "infected":
            return antivirus.ScanResult(clean=False, signature="Win.Test.EICAR_HDB-1")
        return antivirus.ScanResult(clean=True)

    monkeypatch.setattr(antivirus, "scan", fake_scan)
    return state


def _base(wedding, doc):
    v = doc["versions"][0]
    return f"{API}/weddings/{wedding['id']}/documents/{doc['id']}/versions/{v['id']}"


def test_clean_file_scanned_before_extraction(client, alice, wedding, scanner):
    sample = pdf_sample()
    doc = upload(client, alice, wedding, sample, title="Oferta").json()
    assert doc["versions"][0]["scan_status"] == "pending"
    base = _base(wedding, doc)
    # Przed skanem: bez pobierania.
    r = client.get(f"{base}/file", headers=alice)
    assert r.status_code == 409
    assert r.json()["code"] == "document.scan_pending"

    drain_jobs()
    assert scanner["calls"] == 1
    text = client.get(f"{base}/text", headers=alice).json()
    assert text["text_status"] == "done"  # ekstrakcja dopiero po czystym skanie
    assert client.get(f"{base}/file", headers=alice).status_code == 200
    listed = client.get(f"{API}/weddings/{wedding['id']}/documents", headers=alice).json()
    assert listed[0]["versions"][0]["scan_status"] == "clean"

    # Ten sam plik ponownie: wynik skanu przejęty, bez drugiego skanowania.
    again = upload(client, alice, wedding, sample, title="Kopia").json()
    assert again["versions"][0]["scan_status"] == "clean"
    drain_jobs()
    assert scanner["calls"] == 1


def test_infected_file_quarantined(client, alice, wedding, scanner, db):
    scanner["result"] = "infected"
    before = storage_files()
    doc = upload(client, alice, wedding, pdf_sample(), title="Podejrzany").json()
    drain_jobs()
    base = _base(wedding, doc)
    r = client.get(f"{base}/file", headers=alice)
    assert r.status_code == 409
    assert r.json()["code"] == "document.infected"
    text = client.get(f"{base}/text", headers=alice).json()
    assert text["text_status"] == "failed"
    assert "zagrożenie" in text["text_error"]
    assert storage_files() == before  # plik usunięty z magazynu (kwarantanna)
    v = db.scalars(select(DocumentVersion)).one()
    assert v.scan_signature == "Win.Test.EICAR_HDB-1"
    # Ten sam plik drugi raz: odrzucony od razu.
    r = upload(client, alice, wedding, pdf_sample(), title="Jeszcze raz")
    assert r.status_code == 422
    assert r.json()["code"] == "document.infected"
    retry = client.post(f"{base}/retry", headers=alice)
    assert retry.status_code == 409


def test_scanner_down_keeps_file_blocked_and_retries(client, alice, wedding, scanner, db):
    scanner["result"] = "down"
    doc = upload(client, alice, wedding, pdf_sample(), title="Czeka").json()
    drain_jobs()  # zadanie wraca do kolejki z opóźnieniem (nie „przepuszczamy”)
    job = db.scalars(select(Job).where(Job.type == "scan_file")).one()
    assert job.status == "queued"
    assert job.attempts == 1
    assert job.max_attempts == 50
    base = _base(wedding, doc)
    assert client.get(f"{base}/file", headers=alice).json()["code"] == "document.scan_pending"
    assert client.get(f"{base}/text", headers=alice).json()["text_status"] == "pending"

    # Skaner wraca: ponowienie kończy się czystym wynikiem i ekstrakcją.
    scanner["result"] = "clean"
    db.execute(Job.__table__.update().values(run_after=job.created_at))
    db.commit()
    drain_jobs()
    assert client.get(f"{base}/text", headers=alice).json()["text_status"] == "done"


def test_disabled_scanner_marks_not_scanned_and_old_files_queued_later(
    client, alice, wedding, monkeypatch, db
):
    from app.modules.documents import service as documents

    doc = upload(client, alice, wedding, pdf_sample(), title="Bez skanera").json()
    assert doc["versions"][0]["scan_status"] == "not_scanned"
    drain_jobs()
    assert client.get(f"{_base(wedding, doc)}/file", headers=alice).status_code == 200
    assert documents.queue_unscanned(db) == 0  # skaner wyłączony: nic do zrobienia

    # Po wdrożeniu skanera worker sprawdza pliki sprzed wdrożenia.
    monkeypatch.setattr(get_settings(), "clamav_host", "clamav-test")
    monkeypatch.setattr(antivirus, "scan", lambda data: antivirus.ScanResult(clean=True))
    assert documents.queue_unscanned(db) == 1
    drain_jobs()
    assert db.scalars(select(DocumentVersion)).one().scan_status == "clean"


def test_production_requires_scanner(monkeypatch):
    from pydantic import ValidationError

    from app.core.config import Settings

    monkeypatch.setenv("WP_ENV", "prod")
    monkeypatch.setenv("WP_EXPOSE_DOCS", "false")
    monkeypatch.setenv("WP_JWT_SECRET", "p" * 48)
    monkeypatch.delenv("WP_CLAMAV_HOST", raising=False)
    with pytest.raises(ValidationError, match="WP_CLAMAV_HOST"):
        Settings()


@pytest.mark.skipif(
    not os.environ.get("WP_TEST_CLAMAV_HOST"), reason="Ustaw WP_TEST_CLAMAV_HOST (clamd)"
)
def test_real_clamd_detects_eicar(monkeypatch):
    monkeypatch.setattr(get_settings(), "clamav_host", os.environ["WP_TEST_CLAMAV_HOST"])
    assert antivirus.scan(b"zwykly tekst oferty").clean is True
    result = antivirus.scan(EICAR)
    assert result.clean is False
    assert "EICAR" in (result.signature or "").upper()
