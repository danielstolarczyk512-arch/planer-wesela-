"""Wręczanie zaproszeń osobiście (propozycja 4 z docs/analysis/05)."""

from datetime import date

from app.core import clock
from app.modules.guests.delivery import weekends_between

API = "/api/v1"


def test_weekends_between():
    # 2026-10-22 to czwartek: soboty 24.10, 31.10, 7.11.
    assert weekends_between(date(2026, 10, 22), date(2026, 11, 8)) == 3
    assert weekends_between(date(2026, 10, 25), date(2026, 10, 30)) == 0
    assert weekends_between(date(2026, 10, 24), date(2026, 10, 24)) == 1
    assert weekends_between(date(2026, 11, 1), date(2026, 10, 1)) == 0


def add(client, headers, url, name, guests=1, **kw):
    h = client.post(f"{url}/households", headers=headers, json={"name": name, **kw}).json()
    for i in range(guests):
        client.post(
            f"{url}/households/{h['id']}/guests", headers=headers, json={"first_name": f"G{i}"}
        )
    return h


def test_delivery_groups_plan_and_delivered(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2026, 10, 22))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "W", "ceremony_type": "civil", "wedding_date": "2027-06-19"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    babcia = add(
        client, alice, url, "Babcia Zosia", delivery_method="in_person", delivery_place="Tarnów"
    )
    wujek = add(
        client,
        alice,
        url,
        "Wujostwo Nowak",
        3,
        delivery_method="in_person",
        delivery_place=" tarnów ",
    )
    add(client, alice, url, "Kuzyni", 2, delivery_method="in_person", delivery_place="Kraków")
    add(client, alice, url, "Bez miejsca", delivery_method="in_person")
    add(client, alice, url, "Znajomi z pracy", 2, delivery_method="online")
    add(client, alice, url, "Nieustalone")

    o = client.get(f"{url}/invitation-delivery", headers=alice).json()
    assert o["in_person_total"] == 4
    assert o["by_method"] == {"in_person": 4, "online": 1, "none": 1}
    # Do drukarni: 5 papierowych (online nie), zapas co najmniej 3, bez rezerwy.
    assert o["print_order"] == {"printed": 5, "spare": 3, "reserve": 0, "total": 8}
    # Miejscowości łączone bez względu na wielkość liter i spacje; najwięcej do wręczenia na górze.
    assert [g["place"] for g in o["groups"]] == ["Tarnów", "Kraków", None]
    assert [h["name"] for h in o["groups"][0]["households"]] == ["Babcia Zosia", "Wujostwo Nowak"]
    assert o["groups"][0]["households"][1]["guests"] == 3
    # Termin z zadania szablonu „Wręczcie lub wyślijcie zaproszenia” (100 dni przed ślubem).
    assert o["deadline"] == "2027-03-11"
    assert o["weekends_left"] == 20

    r = client.post(
        f"{url}/invitation-delivery/plan",
        headers=alice,
        json={
            "household_ids": [babcia["id"], wujek["id"]],
            "planned_on": "2026-11-07",
            "delivery_by": "Ania i mama",
        },
    )
    assert r.status_code == 200, r.text
    tarnow = r.json()["groups"][0]
    assert tarnow["planned_on"] == ["2026-11-07"]
    assert {h["delivery_by"] for h in tarnow["households"]} == {"Ania i mama"}

    r = client.post(
        f"{url}/invitation-delivery/delivered",
        headers=alice,
        json={"household_ids": [babcia["id"]]},
    )
    o = r.json()
    assert o["in_person_delivered"] == 1
    tarnow = next(g for g in o["groups"] if g["place"] == "Tarnów")
    done = next(h for h in tarnow["households"] if h["id"] == babcia["id"])
    assert (done["invitation_status"], done["delivered_on"]) == ("delivered", "2026-10-22")
    # Gospodarstwo z innego wesela nie przejdzie.
    other = client.post(
        f"{url}/invitation-delivery/delivered",
        headers=alice,
        json={"household_ids": ["0192aaaa-0000-7000-8000-000000000000"]},
    )
    assert other.status_code == 404


def test_household_fields_and_anonymization(client, alice, wedding, db):
    from datetime import timedelta

    from sqlalchemy import select, update

    from app.jobs.worker import run_maintenance
    from app.modules.guests.models import Household
    from app.modules.workspace.models import Wedding

    url = f"{API}/weddings/{wedding['id']}"
    h = add(
        client,
        alice,
        url,
        "Babcia",
        delivery_method="post",
        delivery_place="Nowy Sącz",
        delivery_by="Tata",
    )
    got = client.get(f"{url}/households/{h['id']}", headers=alice).json()
    assert (got["delivery_method"], got["delivery_place"]) == ("post", "Nowy Sącz")
    bad = client.patch(
        f"{url}/households/{h['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"delivery_method": "goląb"},
    )
    assert bad.status_code == 422
    db.execute(update(Wedding).values(wedding_date=clock.today() - timedelta(days=91)))
    db.commit()
    run_maintenance()
    db.expire_all()
    row = db.scalars(select(Household)).one()
    assert (row.delivery_place, row.delivery_by, row.delivery_method) == (None, None, "post")


def test_print_order_spare_and_reserve():
    from app.modules.guests.delivery import print_order
    from app.modules.guests.models import Household

    hs = [Household(delivery_method="online")]
    hs += [Household(delivery_method=None) for _ in range(45)]
    assert print_order(hs, 2) == {"printed": 45, "spare": 5, "reserve": 2, "total": 52}
    assert print_order([Household(delivery_method="online")], 0)["total"] == 0
