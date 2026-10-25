# ruff: noqa: PT018, E501
"""Etap 3: zapytania do firm — zgoda pary, idempotentna wysyłka, błędy SMTP, odpowiedzi → oferta.

Wysyłka idzie prawdziwym protokołem SMTP do małego serwera w teście (`MiniSMTP`), który potrafi
odrzucić adresata, zwrócić 4xx, zerwać połączenie po DATA albo przyjąć wiadomość.
"""

import socket
import socketserver
import threading
from collections.abc import Iterator
from decimal import Decimal
from email import message_from_bytes, policy
from email.message import EmailMessage as EmailMsg
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.jobs import worker
from app.jobs.queue import Job
from app.modules.ai.providers import FakeProvider
from app.modules.catalog.models import CatalogVendor, PublicPackage, VendorFact
from app.modules.concierge.models import VendorPreferences
from app.modules.inquiries import service
from app.modules.inquiries.models import IncomingMessage, Inquiry, InquiryRevision, MailDelivery
from app.modules.offers.models import Offer
from app.modules.vendors.models import Vendor
from tests.api.test_concierge import converse, make_vendor, run_ai_jobs, script
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


class MiniSMTP:
    """Minimalny serwer SMTP: zapisuje przyjęte wiadomości, zachowanie sterowane polami."""

    def __init__(self) -> None:
        self.received: list[bytes] = []
        self.rcpt_reply = b"250 ok\r\n"
        self.data_reply: bytes | None = b"250 ok queued\r\n"  # None = zerwij połączenie po DATA
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                self.wfile.write(b"220 mini ESMTP\r\n")
                data_mode = False
                buf: list[bytes] = []
                while True:
                    line = self.rfile.readline()
                    if not line:
                        return
                    if data_mode:
                        if line == b".\r\n":
                            data_mode = False
                            if outer.data_reply is None:
                                outer.received.append(b"".join(buf))  # serwer przyjął, ale…
                                return  # …zrywa połączenie bez odpowiedzi
                            if outer.data_reply.startswith(b"250"):
                                outer.received.append(b"".join(buf))
                            self.wfile.write(outer.data_reply)
                            buf = []
                        else:
                            buf.append(line)
                        continue
                    cmd = line[:4].upper()
                    if cmd in (b"EHLO", b"HELO"):
                        self.wfile.write(b"250 mini\r\n")
                    elif cmd == b"MAIL":
                        self.wfile.write(b"250 ok\r\n")
                    elif cmd == b"RCPT":
                        self.wfile.write(outer.rcpt_reply)
                    elif cmd == b"DATA":
                        self.wfile.write(b"354 go\r\n")
                        data_mode = True
                    elif cmd == b"QUIT":
                        self.wfile.write(b"221 bye\r\n")
                        return
                    else:
                        self.wfile.write(b"250 ok\r\n")

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def messages(self) -> list[EmailMsg]:
        return [message_from_bytes(raw, policy=policy.default) for raw in self.received]  # type: ignore[misc]


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> Iterator[MiniSMTP]:
    server = MiniSMTP()
    monkeypatch.setenv("WP_SMTP_HOST", "localhost")
    monkeypatch.setenv("WP_SMTP_PORT", str(server.port))
    get_settings.cache_clear()
    yield server
    server.server.shutdown()
    server.server.server_close()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeProvider.responder = None
    yield
    FakeProvider.responder = None
    get_settings.cache_clear()


def w(wedding: dict[str, Any]) -> str:
    return f"{API}/weddings/{wedding['id']}"


def firm(name: str = "Foto Ola", email: str | None = "biuro@fotoola.example", **kw: Any) -> UUID:
    vid = make_vendor(name, **kw)
    if email:
        with get_sessionmaker()() as db:
            db.add(VendorFact(catalog_vendor_id=vid, field="email", value=email, evidence="mailto"))
            db.commit()
    return vid


def draft(
    client: Any, headers: dict[str, str], wedding: dict[str, Any], *vids: UUID, **extra: Any
) -> list[dict[str, Any]]:
    r = client.post(
        f"{w(wedding)}/inquiries",
        headers=headers,
        json={"recipients": [{"catalog_vendor_id": str(v)} for v in vids], **extra},
    )
    assert r.status_code == 201, r.text
    return list(r.json())


def approve(
    client: Any, headers: dict[str, str], wedding: dict[str, Any], inq: dict[str, Any], **over: Any
) -> Any:
    rev = inq["revision"]
    body = {
        "revision_id": rev["id"],
        "content_hash": rev["content_hash"],
        "to_email": rev["to_email"],
        **over,
    }
    return client.post(
        f"{w(wedding)}/inquiries/{inq['id']}/approve-and-send", headers=headers, json=body
    )


def run_sends() -> int:
    n = 0
    while worker.run_once(types=frozenset({service.SEND_JOB})):
        n += 1
        assert n < 20
    return n


def deliveries() -> list[MailDelivery]:
    with get_sessionmaker()() as db:
        return list(db.scalars(select(MailDelivery)))


def count(model: Any, *where: Any) -> int:
    with get_sessionmaker()() as db:
        return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)


# --- szkic i zgoda --------------------------------------------------------------------------


def test_draft_is_private_budget_free_and_sends_nothing(client, alice, wedding, smtp):
    with get_sessionmaker()() as db:
        db.add(
            VendorPreferences(
                wedding_id=UUID(wedding["id"]), category="photographer", budget_max=Decimal("6000")
            )
        )
        db.commit()
    [inq] = draft(client, alice, wedding, firm())
    assert inq["status"] == "draft" and inq["revision"]["number"] == 1 and inq["delivery"] is None
    body = inq["revision"]["body"]
    assert "2027-08" in body and "ok. 110" in body and "Alicja i Bartek" in body
    assert "6000" not in body and "65000" not in body and "bud" not in body.lower()
    assert "dostępność" not in inq["warnings"] and inq["warnings"] == []
    labels = {d["label"] for d in inq["disclosed"]}
    assert {"Termin ślubu", "Liczba gości", "Adres do odpowiedzi (Reply-To)"} <= labels
    assert inq["outbound_enabled"] is True and inq["revision"]["approved_at"] is None
    # powstał prywatny usługodawca z powiązaniem do katalogu; nic nie zostało wysłane
    with get_sessionmaker()() as db:
        pv = db.get_one(Vendor, UUID(inq["vendor_id"]))
        assert pv.catalog_vendor_id is not None and pv.wedding_id == UUID(wedding["id"])
    assert run_sends() == 0 and smtp.received == [] and deliveries() == []


def test_recipient_without_public_email_needs_explicit_address(client, alice, wedding):
    vid = firm("Foto Bez Maila", email=None, phone="+48600999999")
    r = client.post(
        f"{w(wedding)}/inquiries",
        headers=alice,
        json={"recipients": [{"catalog_vendor_id": str(vid)}]},
    )
    assert r.status_code == 422 and r.json()["code"] == "inquiry.no_recipient_email"
    r = client.post(
        f"{w(wedding)}/inquiries",
        headers=alice,
        json={"recipients": [{"catalog_vendor_id": str(vid), "to_email": "Kontakt@Bez.example"}]},
    )
    assert r.status_code == 201 and r.json()[0]["revision"]["to_email"] == "kontakt@bez.example"


def test_approve_sends_once_with_headers_and_double_click_is_idempotent(
    client, alice, wedding, smtp
):
    [inq] = draft(client, alice, wedding, firm())
    r1 = approve(client, alice, wedding, inq)
    r2 = approve(client, alice, wedding, inq)  # podwójne kliknięcie / ponowione żądanie
    assert r1.status_code == r2.status_code == 202, (r1.text, r2.text)
    assert (r1.json()["created"], r2.json()["created"]) == (True, False)
    assert r1.json()["inquiry"]["status"] == "queued"
    assert len(deliveries()) == 1 and count(Job, Job.type == service.SEND_JOB) == 1
    assert run_sends() == 1
    [msg] = smtp.messages()
    assert msg["To"] == "biuro@fotoola.example" and msg["Reply-To"] == "alice@example.com"
    assert msg["Message-ID"].startswith("<") and msg["Subject"].startswith("Zapytanie o ofertę")
    assert "Alicja i Bartek" in msg.get_content()
    done = client.get(f"{w(wedding)}/inquiries/{inq['id']}", headers=alice).json()
    assert done["status"] == "sent" and done["delivery"]["state"] == "accepted"
    assert "nie znaczy, że firma ją odebrała" in done["delivery"]["note"]
    # kolejne zatwierdzenie tej samej rewizji po wysyłce nic nie wysyła
    assert approve(client, alice, wedding, inq).json()["created"] is False
    assert run_sends() == 0 and len(smtp.received) == 1
    # payload zadania nie zawiera treści ani adresata
    with get_sessionmaker()() as db:
        job = db.scalars(select(Job).where(Job.type == service.SEND_JOB)).one()
        assert set(job.payload) == {"delivery_id"}


def test_change_of_content_or_recipient_invalidates_approval(client, alice, wedding, smtp):
    [inq] = draft(client, alice, wedding, firm())
    # zgoda na to, co widziałem; potem ktoś zmienia treść → hash się nie zgadza
    stale = dict(inq["revision"])
    r = client.put(
        f"{w(wedding)}/inquiries/{inq['id']}",
        headers=alice,
        json={
            "base_revision": 1,
            "to_email": "inny@fotoola.example",
            "subject": stale["subject"],
            "body": stale["body"] + "\nPS. Prosimy o szybką odpowiedź.",
        },
    )
    assert (
        r.status_code == 200
        and r.json()["revision"]["number"] == 2
        and r.json()["revision"]["approved_at"] is None
    )
    assert approve(client, alice, wedding, inq).status_code == 409  # rewizja 1 nieaktualna
    assert approve(client, alice, wedding, inq).json()["code"] == "inquiry.stale_revision"
    new = r.json()
    # zgoda wymaga dokładnie tego adresata i hasha
    bad_hash = approve(client, alice, wedding, new, content_hash="0" * 64)
    assert bad_hash.status_code == 409 and bad_hash.json()["code"] == "inquiry.content_changed"
    bad_to = approve(client, alice, wedding, new, to_email="biuro@fotoola.example")
    assert bad_to.status_code == 409 and bad_to.json()["code"] == "inquiry.content_changed"
    assert smtp.received == [] and deliveries() == []
    ok = approve(client, alice, wedding, new)
    assert ok.status_code == 202
    run_sends()
    assert [m["To"] for m in smtp.messages()] == ["inny@fotoola.example"]
    # edycja po wysłaniu to nowa rewizja bez zgody (nic nie wychodzi samo)
    again = client.put(
        f"{w(wedding)}/inquiries/{inq['id']}",
        headers=alice,
        json={
            "base_revision": 2,
            "to_email": "inny@fotoola.example",
            "subject": "Inny temat",
            "body": "Inna treść",
        },
    ).json()
    assert again["status"] == "draft_revised" and again["revision"]["number"] == 3
    assert run_sends() == 0 and len(smtp.received) == 1
    # równoległa edycja: nieaktualna baza → 409
    stale_edit = client.put(
        f"{w(wedding)}/inquiries/{inq['id']}",
        headers=alice,
        json={"base_revision": 2, "to_email": "x@fotoola.example", "subject": "s", "body": "b"},
    )
    assert stale_edit.status_code == 409


def test_budget_in_text_requires_explicit_acknowledgement(client, alice, wedding, smtp):
    [inq] = draft(client, alice, wedding, firm())
    r = client.put(
        f"{w(wedding)}/inquiries/{inq['id']}",
        headers=alice,
        json={
            "base_revision": 1,
            "to_email": inq["revision"]["to_email"],
            "subject": "Zapytanie",
            "body": "Nasz budżet to 65000 zł. Czy macie termin?",
        },
    )
    revised = r.json()
    assert len(revised["warnings"]) == 2  # słowo „budżet” i kwota z ustawień wesela
    denied = approve(client, alice, wedding, revised)
    assert denied.status_code == 422 and denied.json()["code"] == "inquiry.warnings_unacknowledged"
    assert smtp.received == [] and deliveries() == []
    assert approve(client, alice, wedding, revised, acknowledge_warnings=True).status_code == 202


def test_batch_approval_has_one_consent_per_inquiry(client, alice, wedding, smtp):
    a, b, c = draft(
        client,
        alice,
        wedding,
        firm("Foto A", "a@a.example", phone="+48600101010"),
        firm("Foto B", "b@b.example", phone="+48600202020"),
        firm("Foto C", "c@c.example", phone="+48600303030"),
    )
    items = [
        [
            i["id"],
            {
                "revision_id": i["revision"]["id"],
                "content_hash": i["revision"]["content_hash"],
                "to_email": i["revision"]["to_email"],
            },
        ]
        for i in (a, b, c)
    ]
    r = client.post(
        f"{w(wedding)}/inquiries-approve-and-send", headers=alice, json={"items": items}
    )
    assert r.status_code == 202 and [x["created"] for x in r.json()] == [True, True, True]
    run_sends()
    assert sorted(m["To"] for m in smtp.messages()) == ["a@a.example", "b@b.example", "c@c.example"]
    # powtórzenie całej paczki nie wysyła niczego ponownie
    again = client.post(
        f"{w(wedding)}/inquiries-approve-and-send", headers=alice, json={"items": items}
    )
    assert [x["created"] for x in again.json()] == [False, False, False]
    assert run_sends() == 0 and len(smtp.received) == 3


# --- błędy SMTP -----------------------------------------------------------------------------


def delivery_state() -> MailDelivery:
    return deliveries()[0]


def test_rejected_recipient_is_permanent_failure_without_retry(client, alice, wedding, smtp):
    smtp.rcpt_reply = b"550 no such user\r\n"
    [inq] = draft(client, alice, wedding, firm())
    approve(client, alice, wedding, inq)
    assert run_sends() == 1
    d = delivery_state()
    assert (d.state, d.attempts) == ("failed", 1) and "Recipients" in (d.last_error or "")
    assert count(Job, Job.type == service.SEND_JOB, Job.status == "queued") == 0
    out = client.get(f"{w(wedding)}/inquiries/{inq['id']}", headers=alice).json()
    assert out["status"] == "failed" and "Nie udało się wysłać" in out["delivery"]["note"]


def test_temporary_error_is_retried_then_succeeds_without_duplicates(client, alice, wedding, smtp):
    smtp.data_reply = b"451 try later\r\n"
    [inq] = draft(client, alice, wedding, firm())
    approve(client, alice, wedding, inq)
    run_sends()
    assert delivery_state().state == "queued" and delivery_state().attempts == 1
    smtp.data_reply = b"250 ok\r\n"
    with get_sessionmaker()() as db:
        db.execute(
            update(Job)
            .where(Job.type == service.SEND_JOB, Job.status == "queued")
            .values(run_after=utcnow())
        )
        db.commit()
    run_sends()
    d = delivery_state()
    assert (d.state, d.attempts) == ("accepted", 2)
    assert len(smtp.received) == 1  # jedna wiadomość, mimo dwóch prób
    assert smtp.messages()[0]["Message-ID"] == d.message_id


def test_temporary_errors_end_as_failed_after_limit(client, alice, wedding, smtp, monkeypatch):
    monkeypatch.setenv("WP_INQUIRY_SEND_ATTEMPTS", "2")
    get_settings.cache_clear()
    smtp.data_reply = b"451 try later\r\n"
    [inq] = draft(client, alice, wedding, firm())
    approve(client, alice, wedding, inq)
    run_sends()
    with get_sessionmaker()() as db:
        db.execute(
            update(Job)
            .where(Job.type == service.SEND_JOB, Job.status == "queued")
            .values(run_after=utcnow())
        )
        db.commit()
    run_sends()
    d = delivery_state()
    assert (d.state, d.attempts) == ("failed", 2) and smtp.received == []


def test_connection_refused_is_retryable_not_uncertain(client, alice, wedding, smtp, monkeypatch):
    monkeypatch.setenv("WP_SMTP_PORT", "1")  # nic nie nasłuchuje
    get_settings.cache_clear()
    [inq] = draft(client, alice, wedding, firm())
    approve(client, alice, wedding, inq)
    run_sends()
    assert delivery_state().state == "queued"  # bezpieczne ponowienie: serwer niczego nie przyjął


def test_drop_after_data_is_uncertain_and_never_resent(client, alice, wedding, smtp):
    smtp.data_reply = None  # serwer przyjmuje treść i zrywa połączenie bez odpowiedzi
    [inq] = draft(client, alice, wedding, firm())
    approve(client, alice, wedding, inq)
    run_sends()
    d = delivery_state()
    assert d.state == "uncertain" and d.attempts == 1
    assert count(Job, Job.type == service.SEND_JOB, Job.status == "queued") == 0
    # nawet ręczne wywołanie zadania nie wyśle drugi raz
    with get_sessionmaker()() as db:
        service.run_send(db, {"delivery_id": str(d.id)})
    assert len(smtp.received) == 1
    out = client.get(f"{w(wedding)}/inquiries/{inq['id']}", headers=alice).json()
    assert (
        out["status"] == "uncertain"
        and "Nie wysyłamy jej ponownie automatycznie" in out["delivery"]["note"]
    )


def test_worker_crash_during_send_becomes_uncertain_on_requeue(client, alice, wedding, smtp):
    [inq] = draft(client, alice, wedding, firm())
    approve(client, alice, wedding, inq)
    with get_sessionmaker()() as db:  # symulacja: proces zginął po oznaczeniu „sending”
        db.execute(update(MailDelivery).values(state="sending", attempts=1))
        db.commit()
    run_sends()
    assert delivery_state().state == "uncertain" and smtp.received == []


# --- ograniczenia ---------------------------------------------------------------------------


def test_outbound_disabled_unless_local_or_explicitly_enabled(client, alice, wedding, monkeypatch):
    monkeypatch.setenv("WP_SMTP_HOST", "smtp.example.com")
    get_settings.cache_clear()
    [inq] = draft(client, alice, wedding, firm())
    assert inq["outbound_enabled"] is False
    r = approve(client, alice, wedding, inq)
    assert r.status_code == 409 and r.json()["code"] == "inquiry.outbound_disabled"
    assert deliveries() == [] and count(Job, Job.type == service.SEND_JOB) == 0
    monkeypatch.setenv("WP_INQUIRY_REAL_SMTP", "true")
    get_settings.cache_clear()
    assert approve(client, alice, wedding, inq).status_code == 202


def test_per_recipient_and_daily_limits(client, alice, wedding, smtp, monkeypatch):
    monkeypatch.setenv("WP_INQUIRY_MAX_PER_RECIPIENT_PER_DAY", "1")
    monkeypatch.setenv("WP_INQUIRY_MAX_SENDS_PER_DAY", "2")
    get_settings.cache_clear()
    vid = firm()
    [first] = draft(client, alice, wedding, vid)
    assert approve(client, alice, wedding, first).status_code == 202
    [second] = draft(client, alice, wedding, vid)
    assert approve(client, alice, wedding, second).json()["code"] == "inquiry.recipient_limit"
    other = firm("Foto B", "b@b.example", phone="+48600202020")
    [third] = draft(client, alice, wedding, other)
    assert approve(client, alice, wedding, third).status_code == 202
    fourth_vid = firm("Foto C", "c@c.example", phone="+48600303030")
    [fourth] = draft(client, alice, wedding, fourth_vid)
    assert approve(client, alice, wedding, fourth).status_code == 429


# --- uprawnienia i izolacja ------------------------------------------------------------------


def test_roles_and_isolation(client, alice, bob, user_factory, wedding, smtp):
    [inq] = draft(client, alice, wedding, firm())
    babcia = user_factory("babcia@example.com")
    invite_and_accept(client, alice, babcia, wedding, "babcia@example.com", role="viewer")
    assert client.get(f"{w(wedding)}/inquiries/{inq['id']}", headers=babcia).status_code == 200
    assert approve(client, babcia, wedding, inq).status_code == 403  # widz nie zatwierdza
    assert (
        client.put(
            f"{w(wedding)}/inquiries/{inq['id']}",
            headers=babcia,
            json={"base_revision": 1, "to_email": "x@x.example", "subject": "s", "body": "b"},
        ).status_code
        == 403
    )
    kuba = user_factory("kuba@example.com")
    invite_and_accept(client, alice, kuba, wedding, "kuba@example.com", role="coordinator")
    assert (
        client.get(f"{w(wedding)}/inquiries", headers=kuba).status_code == 403
    )  # koordynator nie widzi ofert
    # obce wesele: 404 na wszystko
    other = client.post(
        f"{API}/weddings",
        headers=bob,
        json={"name": "Bob i Celina", "planned_month": "2027-09", "ceremony_type": "civil"},
    ).json()
    assert client.get(f"{w(other)}/inquiries", headers=bob).json() == []
    assert client.get(f"{w(other)}/inquiries/{inq['id']}", headers=bob).status_code == 404
    assert approve(client, bob, other, inq).status_code == 404
    assert client.get(f"{w(wedding)}/inquiries/{inq['id']}", headers=bob).status_code == 404
    assert smtp.received == [] and deliveries() == []


def test_sent_inquiry_cannot_be_deleted_but_draft_can(client, alice, wedding, smtp):
    [a] = draft(client, alice, wedding, firm())
    assert client.delete(f"{w(wedding)}/inquiries/{a['id']}", headers=alice).status_code == 204
    [b] = draft(client, alice, wedding, firm("Foto B", "b@b.example", phone="+48600202020"))
    approve(client, alice, wedding, b)
    assert client.delete(f"{w(wedding)}/inquiries/{b['id']}", headers=alice).status_code == 409


# --- odpowiedzi → szkic oferty -------------------------------------------------------------


def test_manual_response_becomes_offer_draft_without_touching_public_catalog(
    client, alice, wedding, smtp
):
    vid = firm()
    [inq] = draft(client, alice, wedding, vid)
    approve(client, alice, wedding, inq)
    run_sends()
    text = "Dziękujemy za wiadomość.\nTermin jest wolny.\nMenu weselne: 330 zł za osobę dorosłą\nZadatek: 5 000 zł\nMinimalna liczba gości: 80"
    r = client.post(
        f"{w(wedding)}/inquiries/{inq['id']}/import-response",
        headers=alice,
        json={"text": text, "subject": "Re: Zapytanie o ofertę"},
    )
    assert r.status_code == 201, r.text
    resp = r.json()
    assert resp["document_id"] and resp["version_id"]
    out = client.get(f"{w(wedding)}/inquiries/{inq['id']}", headers=alice).json()
    assert out["status"] == "answered" and out["responses"][0]["body"] == text
    # istniejąca ścieżka: wyciąganie tekstu → analiza AI → szkic oferty do zatwierdzenia
    for _ in range(10):
        if not worker.run_once(exclude=frozenset({"send_email"})):
            break
    run = client.post(
        f"{w(wedding)}/inquiries/{inq['id']}/responses/{resp['id']}/analyze", headers=alice
    )
    assert run.status_code == 202, run.text
    for _ in range(10):
        if not worker.run_once(exclude=frozenset({"send_email"})):
            break
    run_id = run.json()["id"]
    done = client.get(f"{w(wedding)}/ai-runs/{run_id}", headers=alice).json()
    assert done["status"] == "succeeded" and done["offer_id"]
    with get_sessionmaker()() as db:
        offer = db.get_one(Offer, UUID(done["offer_id"]))
        assert offer.status == "needs_review" and offer.vendor_id == UUID(inq["vendor_id"])
        # prywatna odpowiedź nie zmienia publicznego cennika
        pkgs = db.scalars(select(PublicPackage).where(PublicPackage.catalog_vendor_id == vid)).all()
        assert [str(p.price_from) for p in pkgs] == ["3500.00"]
        assert db.get_one(CatalogVendor, vid).name == "Foto Ola"


def test_response_validation_and_isolation(client, alice, bob, wedding, smtp):
    [inq] = draft(client, alice, wedding, firm())
    url = f"{w(wedding)}/inquiries/{inq['id']}/import-response"
    assert client.post(url, headers=alice, json={"text": "   "}).status_code == 422
    assert client.post(url, headers=alice, json={"text": "x" * 20_001}).status_code == 422
    other = client.post(
        f"{API}/weddings",
        headers=bob,
        json={"name": "Bob i Celina", "planned_month": "2027-09", "ceremony_type": "civil"},
    ).json()
    assert (
        client.post(
            f"{w(other)}/inquiries/{inq['id']}/import-response",
            headers=bob,
            json={"text": "podszyw"},
        ).status_code
        == 404
    )
    assert count(IncomingMessage) == 0


# --- czat nie wysyła ------------------------------------------------------------------------


def test_chat_prepares_drafts_but_cannot_send(client, alice, wedding, smtp):
    vid = firm()
    script(
        {
            "tool": "draft_inquiry",
            "arguments": {
                "catalog_vendor_ids": [str(vid)],
                "extra_questions": ["Czy robicie też fotobudkę?"],
            },
        },
        {"tool": "send_inquiry", "arguments": {"inquiry_id": "x"}},
        {"tool": "approve_and_send", "arguments": {}},
        {"tool": "get_inquiry_status", "arguments": {}},
        {"tool": "final", "message": "Szkic czeka na Wasze zatwierdzenie w aplikacji."},
    )
    _conv, reply = converse(client, alice, wedding, "zapytaj Foto Ola o termin")
    tools = [(a["tool"], a["ok"]) for a in reply["actions"]]
    assert ("draft_inquiry", True) in tools and ("get_inquiry_status", True) in tools
    draft_action = next(a for a in reply["actions"] if a["tool"] == "draft_inquiry")
    assert len(draft_action["inquiry_ids"]) == 1
    [inq] = client.get(f"{w(wedding)}/inquiries", headers=alice).json()
    assert inq["status"] == "draft" and "fotobudkę" in inq["revision"]["body"]
    assert (
        deliveries() == [] and smtp.received == [] and count(Job, Job.type == service.SEND_JOB) == 0
    )
    assert run_ai_jobs() is None


def test_deleting_wedding_removes_inquiries_but_not_catalog(client, alice, wedding, smtp):
    vid = firm()
    [inq] = draft(client, alice, wedding, vid)
    approve(client, alice, wedding, inq)
    assert client.delete(w(wedding), headers=alice).status_code == 204
    assert count(Inquiry) == 0 and count(InquiryRevision) == 0 and count(MailDelivery) == 0
    assert count(CatalogVendor, CatalogVendor.id == vid) == 1
    _ = socket


def test_wedding_export_contains_search_and_inquiry_data(client, alice, wedding, smtp):
    vid = firm()
    [inq] = draft(client, alice, wedding, vid)
    approve(client, alice, wedding, inq)
    run_sends()
    client.put(
        f"{w(wedding)}/vendor-preferences/photographer", headers=alice, json={"notes": "naturalne"}
    )
    client.post(f"{w(wedding)}/discovery-requests", headers=alice, json={"category": "dj"})
    data = client.get(f"{w(wedding)}/export", headers=alice).json()
    assert [p["notes"] for p in data["vendor_search"]["preferences"]] == ["naturalne"]
    assert (
        len(data["vendor_search"]["candidates"]) == 1
        and len(data["vendor_search"]["discovery_requests"]) == 1
    )
    [exported] = data["inquiries"]
    assert exported["revisions"][0]["subject"] == inq["revision"]["subject"]
    assert [d["state"] for d in exported["deliveries"]] == ["accepted"]
