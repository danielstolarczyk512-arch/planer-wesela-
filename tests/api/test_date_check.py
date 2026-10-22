"""Pomocnik wyboru daty: święta, Adwent/Wielki Post, sezon, zachód słońca."""

from datetime import date, time

from app.core import clock
from app.modules.workspace import dates

API = "/api/v1"


def test_easter_and_movable_holidays():
    assert dates.easter(2026) == date(2026, 4, 5)
    assert dates.easter(2027) == date(2027, 3, 28)
    assert dates.easter(2028) == date(2028, 4, 16)
    h = dates.holidays(2028)
    assert h[date(2028, 6, 15)] == "Boże Ciało"  # Wielkanoc + 60 dni
    assert h[date(2028, 6, 4)] == "Zielone Świątki"
    assert h[date(2028, 12, 24)] == "Wigilia"  # dzień wolny od 2025 r.
    assert date(2024, 12, 24) not in dates.holidays(2024)


def test_church_seasons():
    # Boże Narodzenie 2028 w poniedziałek: Adwent od 3 grudnia.
    assert dates.church_season(date(2028, 12, 2)) is None
    assert dates.church_season(date(2028, 12, 3)) == "Adwent"
    assert dates.church_season(date(2028, 12, 25)) is None
    # Wielkanoc 2028: 16 kwietnia, Popielec 1 marca.
    assert dates.church_season(date(2028, 2, 29)) is None
    assert dates.church_season(date(2028, 3, 1)) == "Wielki Post"
    assert dates.church_season(date(2028, 4, 15)) == "Wielki Post"


def test_sunset_warsaw_and_city_difference():
    def minutes(t: time) -> int:
        return t.hour * 60 + t.minute

    warsaw = dates.sunset(date(2028, 6, 21), *dates.CITIES["Warszawa"])
    assert warsaw is not None
    assert abs(minutes(warsaw) - (21 * 60 + 1)) <= 3
    szczecin = dates.sunset(date(2028, 6, 21), *dates.CITIES["Szczecin"])
    assert szczecin is not None
    assert minutes(szczecin) - minutes(warsaw) > 20


def test_date_check_endpoint(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2027, 10, 1))
    r = client.get(
        f"{API}/date-check",
        headers=alice,
        params=[
            ("date", "2028-06-17"),
            ("date", "2028-03-11"),
            ("date", "2028-06-15"),
            ("ceremony_type", "concordat"),
            ("city", " kraków "),
        ],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["city"] == "Kraków"
    assert "Warszawa" in body["cities"]
    june, lent, feast = body["dates"]
    assert june["weekday"] == "sobota"
    assert june["season"] == "high"
    assert june["holidays_near"] == [{"date": "2028-06-15", "name": "Boże Ciało"}]
    assert june["months_left"] == 8
    assert any("Sobota w szczycie sezonu" in n for n in june["notes"])
    assert any("12-18 miesięcy" in n for n in june["notes"])
    assert june["sunset"]
    assert june["golden_hour_from"] < june["sunset"]
    assert lent["church_season"] == "Wielki Post"
    assert any("parafii" in n for n in lent["notes"])
    assert feast["holiday"] == "Boże Ciało"


def test_date_check_civil_ignores_church_and_requires_login(client, alice):
    r = client.get(
        f"{API}/date-check",
        headers=alice,
        params={"date": "2028-12-09", "ceremony_type": "civil"},
    )
    assert r.json()["dates"][0]["church_season"] is None
    assert r.json()["city"] == "Łódź"
    assert client.get(f"{API}/date-check", params={"date": "2028-12-09"}).status_code == 401
    too_many = [("date", f"2028-07-0{i}") for i in range(1, 8)]
    assert client.get(f"{API}/date-check", headers=alice, params=too_many).status_code == 422


def test_date_check_rejects_out_of_range_years(client, alice):
    r = client.get(f"{API}/date-check", headers=alice, params={"date": "9999-12-31"})
    assert (r.status_code, r.json()["code"]) == (422, "date_check.out_of_range")
