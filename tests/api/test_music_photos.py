"""Muzyka (utwory na momenty, propozycje gości) i zdjęcia grupowe (propozycje 3 i 4, analiza 07)."""

from tests.api.test_offers import vendor
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def _guest(client, headers, w, household, first_name, last_name=None):
    return client.post(
        f"{w}/households/{household['id']}/guests",
        headers=headers,
        json={"first_name": first_name, "last_name": last_name},
    ).json()


def test_music_list_order_and_if_match(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    for moment, title in (
        ("avoid", "Disco polo"),
        ("first_dance", "Perfect"),
        ("entrance", "Intro"),
    ):
        r = client.post(f"{w}/music", headers=alice, json={"moment": moment, "title": title})
        assert r.status_code == 201, r.text
    o = client.get(f"{w}/music", headers=alice).json()
    # Kolejność momentów jak na weselu: wejście, pierwszy taniec … „nie grać” na końcu.
    assert [e["title"] for e in o["entries"]] == ["Intro", "Perfect", "Disco polo"]
    assert o["song_requests"] is False
    e = o["entries"][1]
    url = f"{w}/music/{e['id']}"
    assert client.patch(url, headers=alice, json={"artist": "Ed Sheeran"}).status_code == 428
    r = client.patch(
        url, headers={**alice, "If-Match": f'"{e["version"]}"'}, json={"artist": "Ed Sheeran"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["artist"] == "Ed Sheeran"
    stale = client.patch(
        url, headers={**alice, "If-Match": f'"{e["version"]}"'}, json={"note": "x"}
    )
    assert stale.status_code == 409
    assert client.delete(url, headers=alice).status_code == 204


def test_guest_suggests_song_couple_approves_dj_sees(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    h = client.post(f"{w}/households", headers=alice, json={"name": "Nowakowie"}).json()
    _guest(client, alice, w, h, "Jan")
    token = client.post(f"{w}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]
    song = {"title": "Jolka, Jolka", "artist": "Budka Suflera"}

    # Para nie włączyła propozycji: formularz ich nie pokazuje, a próba kończy się 404.
    assert client.get(f"{API}/rsvp/{token}").json()["songs"]["enabled"] is False
    r = client.post(f"{API}/rsvp/{token}/songs", json=song)
    assert (r.status_code, r.json()["code"]) == (404, "rsvp.songs_disabled")

    on = client.put(f"{w}/music/song-requests", headers=alice, json={"enabled": True})
    assert on.json() == {"enabled": True}
    r = client.post(f"{API}/rsvp/{token}/songs", json=song)
    assert r.status_code == 201, r.text
    assert r.json()["songs"]["mine"] == [song]
    for title in ("Dwa", "Trzy"):
        assert client.post(f"{API}/rsvp/{token}/songs", json={"title": title}).status_code == 201
    over = client.post(f"{API}/rsvp/{token}/songs", json={"title": "Cztery"})
    assert (over.status_code, over.json()["code"]) == (409, "rsvp.songs_limit")

    o = client.get(f"{w}/music", headers=alice).json()
    assert o["waiting"] == 3
    jolka = next(e for e in o["entries"] if e["title"] == "Jolka, Jolka")
    assert (jolka["status"], jolka["suggested_by"], jolka["from_guest"]) == (
        "suggested",
        "Nowakowie",
        True,
    )

    dj = vendor(client, alice, wedding, "DJ Marek", "dj")
    photographer = vendor(client, alice, wedding, "Foto", "photographer")
    dj_token = client.post(f"{w}/vendors/{dj['id']}/day-link", headers=alice).json()["token"]
    ph_token = client.post(f"{w}/vendors/{photographer['id']}/day-link", headers=alice).json()[
        "token"
    ]
    # Niezatwierdzone propozycje nie trafiają do DJ-a.
    day = client.get(f"{API}/day/{dj_token}").json()
    assert day["music"] == []
    assert day["version"] == 1
    r = client.patch(
        f"{w}/music/{jolka['id']}",
        headers={**alice, "If-Match": f'"{jolka["version"]}"'},
        json={"status": "approved"},
    )
    assert r.status_code == 200, r.text
    day = client.get(f"{API}/day/{dj_token}").json()
    assert day["music"] == [
        {"moment": "must", "title": "Jolka, Jolka", "artist": "Budka Suflera", "note": None}
    ]
    assert day["version"] == 2  # nowa lista = nowa wersja do potwierdzenia
    # Fotograf nie widzi muzyki, a jego wersja się nie zmienia.
    assert client.get(f"{API}/day/{ph_token}").json()["music"] == []
    assert client.get(f"{API}/day/{ph_token}").json()["version"] == 1
    # Gość nie widzi, co para odrzuciła — tylko swoje propozycje.
    assert len(client.get(f"{API}/rsvp/{token}").json()["songs"]["mine"]) == 3

    export = client.get(f"{w}/export", headers=alice).json()
    assert len(export["music"]) == 3


def test_viewer_reads_music_but_cannot_write(client, alice, user_factory, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    viewer = user_factory("ogladam@example.com")
    invite_and_accept(client, alice, viewer, wedding, "ogladam@example.com", role="viewer")
    assert client.get(f"{w}/music", headers=viewer).status_code == 200
    r = client.post(f"{w}/music", headers=viewer, json={"moment": "must", "title": "X"})
    assert r.status_code == 403
    r = client.put(f"{w}/music/song-requests", headers=viewer, json={"enabled": True})
    assert r.status_code == 403


def test_photo_groups_typical_people_order_and_coordinator(client, alice, user_factory, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    o = client.post(f"{w}/photo-groups/typical", headers=alice).json()
    assert o["groups"][0]["title"] == "Para Młoda z dziadkami"
    assert o["total_minutes"] == 10 * 3 + 5
    again = client.post(f"{w}/photo-groups/typical", headers=alice).json()
    assert len(again["groups"]) == len(o["groups"])  # bez duplikatów

    h = client.post(f"{w}/households", headers=alice, json={"name": "Dziadkowie"}).json()
    babcia = _guest(client, alice, w, h, "Halina", "Kowalska")
    dziadek = _guest(client, alice, w, h, "Józef")
    first = o["groups"][0]
    url = f"{w}/photo-groups/{first['id']}"
    r = client.patch(
        url,
        headers={**alice, "If-Match": f'"{first["version"]}"'},
        json={"guest_ids": [babcia["id"], dziadek["id"]], "extra": "ksiądz"},
    )
    assert r.status_code == 200, r.text
    g = r.json()["groups"][0]
    assert [p["name"] for p in g["guests"]] == ["Halina Kowalska", "Józef"]
    assert g["version"] == first["version"] + 1
    # Zmiana samego składu też podnosi wersję: stary If-Match dostaje 409.
    stale = client.patch(
        url, headers={**alice, "If-Match": f'"{first["version"]}"'}, json={"guest_ids": []}
    )
    assert stale.status_code == 409

    other = client.post(
        f"{API}/weddings", headers=alice, json={"name": "Inne", "ceremony_type": "civil"}
    ).json()
    oh = client.post(
        f"{API}/weddings/{other['id']}/households", headers=alice, json={"name": "Obcy"}
    ).json()
    stranger = _guest(client, alice, f"{API}/weddings/{other['id']}", oh, "Obcy")
    bad = client.post(
        f"{w}/photo-groups", headers=alice, json={"title": "X", "guest_ids": [stranger["id"]]}
    )
    assert (bad.status_code, bad.json()["code"]) == (422, "photo_group.unknown_guest")

    moved = client.post(f"{url}/move", headers=alice, json={"direction": "down"}).json()
    assert moved["groups"][1]["id"] == first["id"]

    coordinator = user_factory("swiadek@example.com")
    invite_and_accept(
        client, alice, coordinator, wedding, "swiadek@example.com", role="coordinator"
    )
    assert client.get(f"{w}/photo-groups", headers=coordinator).status_code == 200
    done = client.put(f"{url}/done", headers=coordinator, json={"done": True})
    assert done.status_code == 200, done.text
    assert done.json()["remaining_minutes"] == done.json()["total_minutes"] - 3
    r = client.post(f"{w}/photo-groups", headers=coordinator, json={"title": "Y"})
    assert r.status_code == 403

    photographer = vendor(client, alice, wedding, "Foto", "photographer")
    token = client.post(f"{w}/vendors/{photographer['id']}/day-link", headers=alice).json()["token"]
    day = client.get(f"{API}/day/{token}").json()
    group = next(x for x in day["photo_groups"] if x["title"] == "Para Młoda z dziadkami")
    # Fotograf widzi imiona i inicjał nazwiska — bez pełnych danych gości.
    assert group == {
        "title": "Para Młoda z dziadkami",
        "people": ["Halina K.", "Józef"],
        "extra": "ksiądz",
        "minutes": 3,
    }

    # Usunięcie gościa usuwa go z grupy.
    assert client.delete(f"{w}/guests/{babcia['id']}", headers=alice).status_code == 204
    g = client.get(f"{w}/photo-groups", headers=alice).json()["groups"][1]
    assert [p["name"] for p in g["guests"]] == ["Józef"]
