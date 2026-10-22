"""Goście: strona informacyjna, program dla gości, linki RSVP e-mailem, prezenty i podziękowania."""

import re

from sqlalchemy import select

from app.jobs.queue import Job
from tests.api.test_guests import setup_household
from tests.api.test_schedule import add, at

API = "/api/v1"


def test_guest_info_versioned_and_published_in_rsvp(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    empty = client.get(f"{w}/guest-info", headers=alice)
    assert empty.status_code == 200
    assert empty.json()["version"] == 0
    body = {"directions": "Parking za kościołem", "dress_code": "Elegancko", "published": False}
    r = client.put(f"{w}/guest-info", headers={**alice, "If-Match": '"0"'}, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1
    stale = client.put(f"{w}/guest-info", headers={**alice, "If-Match": '"0"'}, json=body)
    assert stale.status_code == 409

    _, _, _, h, *_ = setup_household(client, alice, wedding)
    add(client, alice, wedding, title="Ceremonia", starts_at=at("15:00"), for_guests=True)
    add(client, alice, wedding, title="Sesja w ogrodzie", starts_at=at("17:00"))
    token = client.post(f"{w}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]
    view = client.get(f"{API}/rsvp/{token}").json()
    assert view["info"] is None  # nieopublikowane
    assert [s["title"] for s in view["schedule"]] == ["Ceremonia"]

    client.put(
        f"{w}/guest-info", headers={**alice, "If-Match": '"1"'}, json={**body, "published": True}
    )
    info = client.get(f"{API}/rsvp/{token}").json()["info"]
    assert info["directions"] == "Parking za kościołem"


def test_rsvp_emails_preview_and_send(client, alice, wedding, db):
    w = f"{API}/weddings/{wedding['id']}"
    _, _, _, h, *_ = setup_household(client, alice, wedding)
    no_email = client.post(
        f"{w}/households", headers=alice, json={"name": "Wujek bez maila"}
    ).json()
    client.post(
        f"{w}/households/{no_email['id']}/guests", headers=alice, json={"first_name": "Zenek"}
    )

    preview = client.post(f"{w}/rsvp-emails", headers=alice, json={"dry_run": True})
    assert preview.status_code == 200, preview.text
    p = preview.json()
    assert [t["household_id"] for t in p["to_send"]] == [h["id"]]
    assert p["without_email"] == 1

    sent = client.post(f"{w}/rsvp-emails", headers=alice, json={"dry_run": False}).json()
    assert len(sent["to_send"]) == 1
    job = db.scalars(select(Job).where(Job.type == "send_email")).all()[-1]
    assert job.payload["to"] == "nowak@example.com"
    token = re.search(r"/rsvp/([A-Za-z0-9_\-]+)", job.payload["body"]).group(1)
    assert client.get(f"{API}/rsvp/{token}").status_code == 200
    # Wersja HTML z tym samym linkiem; gość nie ma konta — bez linku do ustawień.
    assert f"/rsvp/{token}" in job.payload["html"]
    assert "Potwierdź obecność" in job.payload["html"]
    assert "Zmień powiadomienia" not in job.payload["html"]
    households = client.get(f"{w}/households", headers=alice).json()
    assert next(x for x in households if x["id"] == h["id"])["rsvp_emailed_at"] is not None

    # Ma już aktywny link: domyślnie pomijamy (nie psujemy wysłanego linku).
    again = client.post(f"{w}/rsvp-emails", headers=alice, json={"dry_run": True}).json()
    assert again["to_send"] == []
    assert again["with_link_skipped"] == 1
    forced = client.post(
        f"{w}/rsvp-emails", headers=alice, json={"dry_run": False, "include_with_link": True}
    ).json()
    assert len(forced["to_send"]) == 1
    assert client.get(f"{API}/rsvp/{token}").status_code == 404  # stary link przestał działać


def test_gift_note_and_thanks(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    _, _, _, h, *_ = setup_household(client, alice, wedding)
    r = client.patch(
        f"{w}/households/{h['id']}",
        headers={**alice, "If-Match": f'"{h["version"]}"'},
        json={"gift_note": "Koperta i ekspres do kawy", "thanked": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["gift_note"] == "Koperta i ekspres do kawy"
    assert r.json()["thanked"] is True


def test_rsvp_qr_cards_and_link_qr(client, alice, wedding):
    import segno

    w = f"{API}/weddings/{wedding['id']}"
    _, _, _, linked, *_ = setup_household(client, alice, wedding)
    client.post(f"{w}/households", headers=alice, json={"name": "Państwo Zając"})

    link = client.post(f"{w}/households/{linked['id']}/rsvp-link", headers=alice).json()
    expected = segno.make(link["url"], error="m").svg_inline(
        scale=4, border=2, dark="#000", light="#fff"
    )
    assert link["qr_svg"] == expected  # kod QR koduje dokładnie adres z tokenem
    old_token = link["token"]

    # Podgląd: rodzina z aktywnym linkiem pominięta, bez tworzenia linków.
    r = client.post(f"{w}/rsvp-qr", headers=alice, json={"dry_run": True})
    assert r.status_code == 200, r.text
    preview = r.json()
    assert [c["name"] for c in preview["cards"]] == ["Państwo Zając"]
    assert preview["cards"][0]["url"] is None
    assert preview["with_link_skipped"] == 1

    r = client.post(f"{w}/rsvp-qr", headers=alice, json={"dry_run": False})
    card = r.json()["cards"][0]
    assert card["qr_svg"].startswith("<svg")
    new_token = card["url"].rsplit("/", 1)[1]
    assert client.get(f"{API}/rsvp/{new_token}").json()["household_name"] == "Państwo Zając"
    assert client.get(f"{API}/rsvp/{old_token}").status_code == 200  # nietknięty

    # Wybrane rodziny i „wygeneruj nowe”: stary link przestaje działać.
    r = client.post(
        f"{w}/rsvp-qr",
        headers=alice,
        json={"household_ids": [linked["id"]], "include_with_link": True, "dry_run": False},
    )
    assert [c["household_id"] for c in r.json()["cards"]] == [linked["id"]]
    assert client.get(f"{API}/rsvp/{old_token}").status_code == 404
    foreign = client.post(
        f"{w}/rsvp-qr",
        headers=alice,
        json={"household_ids": ["0192e000-0000-7000-8000-000000000000"]},
    )
    assert foreign.status_code == 404


def test_guest_page_theme_in_rsvp(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    _, _, _, h, *_ = setup_household(client, alice, wedding)
    token = client.post(f"{w}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]
    assert client.get(f"{API}/rsvp/{token}").json()["theme"] == {
        "style": "classic",
        "accent": None,
    }
    bad = client.put(
        f"{w}/guest-info", headers={**alice, "If-Match": '"0"'}, json={"theme": "neon"}
    )
    assert bad.status_code == 422
    r = client.put(
        f"{w}/guest-info",
        headers={**alice, "If-Match": '"0"'},
        json={"theme": "garden", "accent": "sage"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["theme"] == "garden"
    assert client.get(f"{API}/rsvp/{token}").json()["theme"] == {
        "style": "garden",
        "accent": "sage",
    }


def test_guest_page_preview_for_couple(client, alice, bob, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    _, _, _, h, *_ = setup_household(client, alice, wedding)
    client.put(
        f"{w}/guest-info",
        headers={**alice, "If-Match": '"0"'},
        json={"directions": "Parking za dworkiem", "theme": "modern", "published": False},
    )
    add(client, alice, wedding, title="Ceremonia", starts_at=at("15:00"), for_guests=True)
    r = client.get(f"{w}/guest-info/preview", headers=alice)
    assert r.status_code == 200, r.text
    view = r.json()
    # Szkic informacji widoczny w podglądzie, z informacją, że goście go jeszcze nie widzą.
    assert view["info"]["directions"] == "Parking za dworkiem"
    assert view["preview_info_published"] is False
    assert view["theme"]["style"] == "modern"
    assert [s["title"] for s in view["schedule"]] == ["Ceremonia"]
    # Fikcyjna rodzina zamiast prawdziwych gości (bez danych osobowych).
    assert view["household_name"] == "Przykładowa rodzina"
    assert "Nowak" not in r.text
    assert {g["first_name"] for g in view["guests"]} == {"Anna", "Jan", "Zosia"}
    # Prawdziwy link gościa nadal nie pokazuje nieopublikowanych informacji.
    token = client.post(f"{w}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]
    assert client.get(f"{API}/rsvp/{token}").json()["info"] is None
    assert client.get(f"{w}/guest-info/preview", headers=bob).status_code == 404


def test_guests_csv_export_for_excel(client, alice, bob, wedding, db):
    import csv
    import io

    from app.modules.audit.models import AuditLog

    w = f"{API}/weddings/{wedding['id']}"
    _, reception, _, _, adult, _ = setup_household(client, alice, wedding)
    client.patch(
        f"{w}/guests/{adult['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"dietary_preference": "vegan", "dietary_note": "alergia na orzechy"},
    )
    client.put(
        f"{w}/guests/{adult['id']}/attendance/{reception['id']}",
        headers=alice,
        json={"status": "attending"},
    )
    evil = client.post(f"{w}/households", headers=alice, json={"name": "=HYPERLINK(1)"}).json()
    client.post(f"{w}/households/{evil['id']}/guests", headers=alice, json={"first_name": "Ola"})

    r = client.get(f"{w}/guests/export.csv", headers=alice)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith("﻿".encode())  # BOM: polski Excel rozpozna UTF-8
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][:6] == ["Zaproszenie", "Imię", "Nazwisko", "Wiek", "Przyjęcie", "Dieta"]
    assert "Uwagi dla kuchni" not in rows[0]
    jan = next(row for row in rows if row[1] == "Jan")
    assert jan[3:6] == ["dorosły", "będzie", "wegańska"]
    assert "orzechy" not in r.content.decode("utf-8-sig")
    assert rows[0][-4:] == ["Wręczenie", "Miejscowość", "Kurs", "Pokój"]
    # Formuła w nazwie zaproszenia neutralizowana apostrofem.
    assert next(row for row in rows if row[1] == "Ola")[0] == "'=HYPERLINK(1)"

    # Uwagi dietetyczne tylko na życzenie — z wpisem w audycie.
    r = client.get(f"{w}/guests/export.csv", headers=alice, params={"include_notes": "true"})
    assert "alergia na orzechy" in r.content.decode("utf-8-sig")
    logged = db.scalars(select(AuditLog).where(AuditLog.action == "export_csv")).all()
    assert [entry.changes["include_notes"][1] for entry in logged] == [False, True]
    assert client.get(f"{w}/guests/export.csv", headers=bob).status_code == 404


def test_household_language_drives_rsvp_email_and_page(client, alice, wedding, db):
    w = f"{API}/weddings/{wedding['id']}"
    h = client.post(
        f"{w}/households",
        headers=alice,
        json={"name": "Smith family", "contact_email": "smith@example.com", "language": "en"},
    ).json()
    assert h["language"] == "en"
    client.post(f"{w}/households/{h['id']}/guests", headers=alice, json={"first_name": "John"})
    client.post(f"{w}/rsvp-emails", headers=alice, json={"dry_run": False})
    job = db.scalars(select(Job).where(Job.type == "send_email")).all()[-1]
    assert job.payload["to"] == "smith@example.com"
    assert "please confirm your attendance" in job.payload["subject"]
    assert "Confirm attendance" in job.payload["html"]
    assert '<html lang="en">' in job.payload["html"]
    token = re.search(r"/rsvp/([A-Za-z0-9_\-]+)", job.payload["body"]).group(1)
    assert client.get(f"{API}/rsvp/{token}").json()["language"] == "en"

    bad = client.patch(
        f"{w}/households/{h['id']}", headers={**alice, "If-Match": '"1"'}, json={"language": "de"}
    )
    assert bad.status_code == 422
    # Wysyłka zapisała rsvp_emailed_at — aktualna wersja zaproszenia z listy.
    version = next(
        x for x in client.get(f"{w}/households", headers=alice).json() if x["id"] == h["id"]
    )["version"]
    r = client.patch(
        f"{w}/households/{h['id']}",
        headers={**alice, "If-Match": f'"{version}"'},
        json={"language": "pl"},
    )
    assert r.json()["language"] == "pl"


def test_english_rsvp_mail_month_name_without_locale():
    from datetime import date

    from app.modules.guests.models import Household
    from app.modules.guests.service import rsvp_mail

    h = Household(name="Smith family", language="en", rsvp_deadline=date(2028, 5, 3))
    mail = rsvp_mail("Anna & Tom", h, "https://example.com/rsvp/x")
    assert "by 3 May 2028" in mail.text
