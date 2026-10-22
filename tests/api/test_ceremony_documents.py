"""Licznik ważności dokumentów do ślubu (propozycja 7 z docs/analysis/05)."""

from datetime import date

from app.core import clock
from app.modules.planner.documents import BY_CODE, add_months, evaluate

API = "/api/v1"


def test_add_months_handles_month_end():
    assert add_months(date(2028, 7, 1), -6) == date(2028, 1, 1)
    assert add_months(date(2027, 8, 31), -6) == date(2027, 2, 28)
    assert add_months(date(2027, 1, 31), 1) == date(2027, 2, 28)


def test_evaluate_windows_and_expiry():
    rule = BY_CODE["usc_certificate"]
    day = date(2028, 7, 1)
    early = evaluate(rule, day, date(2027, 10, 1))
    assert (early["status"], early["earliest"], early["latest"]) == (
        "too_early",
        date(2028, 1, 1),
        date(2028, 6, 1),
    )
    assert evaluate(rule, day, date(2028, 3, 1))["status"] == "now"
    assert evaluate(rule, day, date(2028, 6, 20))["status"] == "late"
    # Wydane za wcześnie: traci ważność przed ślubem.
    bad = evaluate(rule, day, date(2028, 3, 1), issued_on=date(2027, 12, 15))
    assert (bad["status"], bad["expires_on"]) == ("expires", date(2028, 6, 15))
    assert evaluate(rule, day, date(2028, 3, 1), issued_on=date(2028, 2, 1))["status"] == "ok"
    # Bez daty ślubu nie liczymy okien.
    assert evaluate(rule, None, date(2028, 3, 1))["status"] == "no_date"


def test_civil_and_concordat_lists(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2028, 3, 1))
    civil = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "Cywilny", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    r = client.get(f"{API}/weddings/{civil['id']}/ceremony-documents", headers=alice)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [i["code"] for i in items] == ["usc_assurance"]
    assert items[0]["latest"] == "2028-05-31"  # miesiąc (31 dni) przed ślubem
    assert items[0]["source"].startswith("https://www.gov.pl/")

    church = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "Kościelny", "ceremony_type": "concordat", "planned_month": "2028-07"},
    ).json()
    url = f"{API}/weddings/{church['id']}/ceremony-documents"
    body = client.get(url, headers=alice).json()
    assert body["approximate"] is True
    codes = {i["code"] for i in body["items"]}
    assert codes == {"usc_certificate", "baptism", "parish_protocol"}

    # Świadectwo chrztu: parafia wymaga 3 miesięcy; wydane w listopadzie traci ważność.
    r = client.put(
        f"{url}/baptism", headers=alice, json={"issued_on": "2027-11-20", "valid_months": 3}
    )
    assert r.status_code == 200, r.text
    baptism = next(i for i in r.json()["items"] if i["code"] == "baptism")
    assert (baptism["status"], baptism["expires_on"]) == ("expires", "2028-02-20")
    # Ważność z przepisów (USC) nie jest do zmiany; spotkanie w parafii nie ma daty wydania.
    fixed = client.put(f"{url}/usc_certificate", headers=alice, json={"valid_months": 12})
    assert fixed.json()["code"] == "ceremony_document.validity_fixed"
    no_date = client.put(f"{url}/parish_protocol", headers=alice, json={"issued_on": "2028-01-01"})
    assert no_date.json()["code"] == "ceremony_document.no_issue_date"
    done = client.put(f"{url}/parish_protocol", headers=alice, json={"done": True})
    assert (
        next(i for i in done.json()["items"] if i["code"] == "parish_protocol")["status"] == "done"
    )
    assert client.put(f"{url}/nieznany", headers=alice, json={}).status_code == 404


def test_viewer_cannot_save(client, alice, user_factory, wedding):
    from tests.api.test_workspace import invite_and_accept

    viewer = user_factory("babcia@example.com")
    invite_and_accept(client, alice, viewer, wedding, "babcia@example.com", role="viewer")
    url = f"{API}/weddings/{wedding['id']}/ceremony-documents"
    assert client.get(url, headers=viewer).status_code == 200
    assert client.put(f"{url}/baptism", headers=viewer, json={"done": True}).status_code == 403
