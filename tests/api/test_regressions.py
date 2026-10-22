"""Regresje znalezione przez testy kontraktowe (Schemathesis), Etap 3."""

import pytest

API = "/api/v1"


@pytest.mark.parametrize(
    "body",
    [
        {"name": "X", "planned_month": "0000-01"},
        {"name": "X", "planned_month": "2019-05"},
        {"name": "X", "wedding_date": "9999-12-31"},
    ],
)
def test_wedding_dates_out_of_range_are_422_not_500(client, alice, body):
    r = client.post(f"{API}/weddings", headers=alice, json=body)
    assert r.status_code == 422, r.text


def test_reschedule_rejects_far_future(client, alice, wedding):
    r = client.post(
        f"{API}/weddings/{wedding['id']}/reschedule",
        headers={**alice, "If-Match": '"1"'},
        json={"wedding_date": "9999-12-31"},
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("", {"ceremony_type": None}),
        ("", {"name": None}),
    ],
)
def test_patch_explicit_null_on_required_field_is_422(client, alice, wedding, path, body):
    r = client.patch(
        f"{API}/weddings/{wedding['id']}{path}", headers={**alice, "If-Match": '"1"'}, json=body
    )
    assert r.status_code == 422, r.text


def test_patch_task_null_title_is_422(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/tasks"
    task = client.post(url, headers=alice, json={"title": "A"}).json()
    r = client.patch(
        f"{url}/{task['id']}", headers={**alice, "If-Match": '"1"'}, json={"title": None}
    )
    assert r.status_code == 422


def test_nul_byte_in_text_is_422(client, alice, wedding):
    r = client.post(
        f"{API}/weddings/{wedding['id']}/households", headers=alice, json={"name": "Nowak\u0000"}
    )
    assert r.status_code == 422
    assert r.json()["code"] == "validation.invalid_value"


@pytest.mark.parametrize(
    "csv",
    [
        "household;first_name\nA;B\rC\n",  # \r w polu bez cudzysłowu
        'household;first_name\n"A;B\n',  # niezamknięty cudzysłów
        "household;first_name\nA;B;C;D\n",  # nadmiarowe kolumny
    ],
)
def test_malformed_csv_never_500(client, alice, wedding, csv):
    r = client.post(
        f"{API}/weddings/{wedding['id']}/guests/import", headers=alice, json={"csv": csv}
    )
    assert r.status_code in (200, 422), r.text
