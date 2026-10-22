from datetime import datetime, timedelta

import pytest

from app.modules.workspace.schemas import WARSAW
from tests.conftest import token_from_last_email

API = "/api/v1"


def _w(wedding):
    return f"{API}/weddings/{wedding['id']}"


def invite_and_accept(
    client, owner, member_headers, wedding, email, role="coorganizer", funder_id=None
):
    body = {"email": email, "role": role, **({"funder_id": funder_id} if funder_id else {})}
    r = client.post(f"{_w(wedding)}/invitations", headers=owner, json=body)
    assert r.status_code == 201, r.text
    r = client.post(
        f"{API}/invitations/accept",
        headers=member_headers,
        json={"token": token_from_last_email(email)},
    )
    assert r.status_code == 200, r.text
    return r.json()


# --- wesela -------------------------------------------------------------------------


def test_create_wedding_returns_money_as_string(wedding):
    assert wedding["total_budget"] == {"amount": "65000.00", "currency": "PLN"}
    assert wedding["planned_month"] == "2027-08"
    assert wedding["my_role"] == "owner"
    assert wedding["version"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "X", "wedding_date": "2020-01-01"},
        {"name": "X", "wedding_date": "2030-06-01", "planned_month": "2030-06"},
        {"name": "X", "planned_month": "2030-13"},
        {"name": "X", "guest_count_planned": -1},
        {"name": "X", "total_budget": {"amount": "10.999", "currency": "PLN"}},
        {"name": "X", "total_budget": {"amount": "10.00", "currency": "EUR"}},
        {"name": "X", "colors": ["a"] * 11},
    ],
)
def test_create_wedding_validation(client, alice, payload):
    r = client.post(f"{API}/weddings", headers=alice, json=payload)
    assert r.status_code == 422, r.text


def test_list_weddings_with_cursor(client, alice):
    for i in range(3):
        client.post(f"{API}/weddings", headers=alice, json={"name": f"Wesele {i}"})
    page1 = client.get(f"{API}/weddings?limit=2", headers=alice).json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"]
    page2 = client.get(
        f"{API}/weddings?limit=2&cursor={page1['next_cursor']}", headers=alice
    ).json()
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None
    ids = {w["id"] for w in page1["items"] + page2["items"]}
    assert len(ids) == 3


def test_update_wedding_requires_if_match_and_detects_conflict(client, alice, wedding):
    url = _w(wedding)
    assert client.patch(url, headers=alice, json={"city": "Gdańsk"}).status_code == 428

    r = client.patch(url, headers={**alice, "If-Match": '"1"'}, json={"city": "Gdańsk"})
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert r.headers["ETag"] == '"2"'

    stale = client.patch(url, headers={**alice, "If-Match": '"1"'}, json={"city": "Sopot"})
    assert stale.status_code == 409
    assert stale.json()["code"] == "conflict.version_mismatch"
    assert client.get(url, headers=alice).json()["city"] == "Gdańsk"


def test_setting_date_clears_planned_month(client, alice, wedding):
    future = (datetime.now(WARSAW).date() + timedelta(days=400)).isoformat()
    # Zadania mają już terminy liczone od planowanego miesiąca: PATCH wymaga /reschedule.
    r = client.patch(
        _w(wedding), headers={**alice, "If-Match": '"1"'}, json={"wedding_date": future}
    )
    assert r.status_code == 409
    assert r.json()["code"] == "wedding.reschedule_required"
    r = client.post(
        f"{_w(wedding)}/reschedule",
        headers={**alice, "If-Match": '"1"'},
        json={"wedding_date": future, "dry_run": False},
    )
    assert r.status_code == 200, r.text
    w = client.get(_w(wedding), headers=alice).json()
    assert w["wedding_date"] == future
    assert w["planned_month"] is None


def test_delete_wedding_owner_only(client, alice, bob, wedding):
    invite_and_accept(client, alice, bob, wedding, "bob@example.com")
    assert client.delete(_w(wedding), headers=bob).status_code == 403
    assert client.delete(_w(wedding), headers=alice).status_code == 204
    assert client.get(_w(wedding), headers=alice).status_code == 404


# --- wydarzenia -----------------------------------------------------------------------


def test_events_crud(client, alice, wedding):
    url = f"{_w(wedding)}/events"
    r = client.post(
        url,
        headers=alice,
        json={
            "kind": "reception",
            "name": "Przyjęcie",
            "starts_at": "2027-08-21T17:00:00+02:00",
            "ends_at": "2027-08-22T04:00:00+02:00",
        },
    )
    assert r.status_code == 201, r.text
    event = r.json()
    client.post(url, headers=alice, json={"kind": "after_party", "name": "Poprawiny"})
    assert [e["kind"] for e in client.get(url, headers=alice).json()] == [
        "reception",
        "after_party",
    ]

    r = client.patch(
        f"{url}/{event['id']}", headers={**alice, "If-Match": '"1"'}, json={"name": "Wesele"}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Wesele"
    assert client.delete(f"{url}/{event['id']}", headers=alice).status_code == 204
    assert client.get(f"{url}/{event['id']}", headers=alice).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "party", "name": "X"},
        {"kind": "reception", "name": "X", "starts_at": "2027-08-21T17:00:00"},
        {
            "kind": "reception",
            "name": "X",
            "starts_at": "2027-08-21T17:00:00+02:00",
            "ends_at": "2027-08-21T16:00:00+02:00",
        },
    ],
)
def test_event_validation(client, alice, wedding, payload):
    assert client.post(f"{_w(wedding)}/events", headers=alice, json=payload).status_code == 422


def test_event_patch_cannot_break_time_range(client, alice, wedding):
    url = f"{_w(wedding)}/events"
    e = client.post(
        url,
        headers=alice,
        json={
            "kind": "ceremony",
            "name": "Ślub",
            "starts_at": "2027-08-21T15:00:00+02:00",
            "ends_at": "2027-08-21T16:00:00+02:00",
        },
    ).json()
    r = client.patch(
        f"{url}/{e['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"ends_at": "2027-08-21T14:00:00+02:00"},
    )
    assert r.status_code == 422


# --- członkowie i zaproszenia -------------------------------------------------------------


def test_invitation_flow_and_roles(client, alice, bob, wedding):
    joined = invite_and_accept(client, alice, bob, wedding, "bob@example.com")
    assert joined["my_role"] == "coorganizer"
    members = client.get(f"{_w(wedding)}/members", headers=bob).json()
    assert {m["role"] for m in members} == {"owner", "coorganizer"}
    # Współorganizator może edytować, ale nie zarządzać członkami.
    r = client.patch(_w(wedding), headers={**bob, "If-Match": '"1"'}, json={"city": "Łódź"})
    assert r.status_code == 200
    assert client.get(f"{_w(wedding)}/invitations", headers=bob).status_code == 403


def test_viewer_is_read_only(client, alice, user_factory, wedding):
    viewer = user_factory("babcia@example.com")
    invite_and_accept(client, alice, viewer, wedding, "babcia@example.com", role="viewer")
    assert client.get(_w(wedding), headers=viewer).status_code == 200
    r = client.patch(_w(wedding), headers={**viewer, "If-Match": '"1"'}, json={"city": "X"})
    assert r.status_code == 403
    r = client.post(f"{_w(wedding)}/events", headers=viewer, json={"kind": "other", "name": "X"})
    assert r.status_code == 403


def test_invitation_for_other_email_is_not_found(client, alice, bob, user_factory, wedding):
    client.post(
        f"{_w(wedding)}/invitations",
        headers=alice,
        json={"email": "bob@example.com", "role": "coorganizer"},
    )
    token = token_from_last_email("bob@example.com")
    mallory = user_factory("mallory@example.com")
    r = client.post(f"{API}/invitations/accept", headers=mallory, json={"token": token})
    assert r.status_code == 404


def test_invitation_single_use_and_revocation(client, alice, bob, wedding):
    invite_and_accept(client, alice, bob, wedding, "bob@example.com")
    r = client.post(
        f"{_w(wedding)}/invitations", headers=alice, json={"email": "carol@example.com"}
    )
    inv = r.json()
    assert client.delete(f"{_w(wedding)}/invitations/{inv['id']}", headers=alice).status_code == 204
    assert client.delete(f"{_w(wedding)}/invitations/{inv['id']}", headers=alice).status_code == 404


def test_unverified_user_cannot_invite(client, user_factory):
    h = user_factory("nowy@example.com", verify=False)
    w = client.post(f"{API}/weddings", headers=h, json={"name": "Test"}).json()
    r = client.post(
        f"{API}/weddings/{w['id']}/invitations", headers=h, json={"email": "x@example.com"}
    )
    assert r.status_code == 403
    assert r.json()["code"] == "auth.email_not_verified"


def test_last_owner_protection(client, alice, bob, wedding):
    alice_id = client.get(f"{API}/me", headers=alice).json()["id"]
    bob_id = client.get(f"{API}/me", headers=bob).json()["id"]
    invite_and_accept(client, alice, bob, wedding, "bob@example.com")
    r = client.patch(f"{_w(wedding)}/members/{alice_id}", headers=alice, json={"role": "viewer"})
    assert r.status_code == 409
    assert client.delete(f"{_w(wedding)}/members/{alice_id}", headers=alice).status_code == 409

    # Przekazanie roli właściciela, potem odejście.
    r = client.patch(f"{_w(wedding)}/members/{bob_id}", headers=alice, json={"role": "owner"})
    assert r.status_code == 200
    assert client.delete(f"{_w(wedding)}/members/{alice_id}", headers=alice).status_code == 204
    assert client.get(_w(wedding), headers=alice).status_code == 404


def test_member_can_leave(client, alice, bob, wedding):
    bob_id = client.get(f"{API}/me", headers=bob).json()["id"]
    invite_and_accept(client, alice, bob, wedding, "bob@example.com")
    assert client.delete(f"{_w(wedding)}/members/{bob_id}", headers=bob).status_code == 204
    assert client.get(_w(wedding), headers=bob).status_code == 404
