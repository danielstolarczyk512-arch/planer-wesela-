"""Lista prezentów z rezerwacją gości i komentarze przy zadaniach (N4, N6 z analizy 08)."""

from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def _household(client, headers, w, name):
    h = client.post(f"{w}/households", headers=headers, json={"name": name}).json()
    client.post(f"{w}/households/{h['id']}/guests", headers=headers, json={"first_name": "Jan"})
    token = client.post(f"{w}/households/{h['id']}/rsvp-link", headers=headers).json()["token"]
    return h, token


def test_gifts_reserved_once_and_visible_to_couple(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    _, nowak = _household(client, alice, w, "Nowakowie")
    _, kowal = _household(client, alice, w, "Kowalscy")
    r = client.post(f"{w}/gifts", headers=alice, json={"title": "Ekspres", "link": "ftp://x"})
    assert r.status_code == 422
    o = client.post(
        f"{w}/gifts",
        headers=alice,
        json={"title": "Ekspres", "link": "https://sklep.example/ekspres"},
    ).json()
    o = client.post(
        f"{w}/gifts", headers=alice, json={"kind": "fund", "title": "Podróż poślubna"}
    ).json()
    ekspres, fund = o["ideas"]
    assert client.get(f"{API}/rsvp/{nowak}").json()["gifts"] is None
    r = client.put(f"{API}/rsvp/{nowak}/gifts/{ekspres['id']}", json={"reserved": True})
    assert (r.status_code, r.json()["code"]) == (404, "rsvp.gifts_disabled")

    s = client.put(f"{w}/guest-page", headers=alice, json={"gifts_enabled": True}).json()
    assert s["gifts_enabled"] is True
    view = client.put(f"{API}/rsvp/{nowak}/gifts/{ekspres['id']}", json={"reserved": True}).json()
    assert [(g["title"], g["reserved"], g["mine"]) for g in view["gifts"]] == [
        ("Ekspres", True, True),
        ("Podróż poślubna", False, False),
    ]
    # Inna rodzina widzi tylko „zarezerwowane” i nie przejmie prezentu.
    other = client.get(f"{API}/rsvp/{kowal}").json()["gifts"][0]
    assert (other["reserved"], other["mine"]) == (True, False)
    taken = client.put(f"{API}/rsvp/{kowal}/gifts/{ekspres['id']}", json={"reserved": True})
    assert (taken.status_code, taken.json()["code"]) == (409, "gift.taken")
    # Cudzej rezerwacji nie zwolni; funduszu nie rezerwuje się.
    client.put(f"{API}/rsvp/{kowal}/gifts/{ekspres['id']}", json={"reserved": False})
    r = client.put(f"{API}/rsvp/{kowal}/gifts/{fund['id']}", json={"reserved": True})
    assert (r.status_code, r.json()["code"]) == (409, "gift.not_reservable")

    couple = client.get(f"{w}/gifts", headers=alice).json()
    assert couple["ideas"][0]["reserved_by"] == "Nowakowie"
    assert couple["reserved_count"] == 1
    view = client.put(f"{API}/rsvp/{nowak}/gifts/{ekspres['id']}", json={"reserved": False}).json()
    assert view["gifts"][0]["reserved"] is False
    assert len(client.get(f"{w}/export", headers=alice).json()["gift_ideas"]) == 2


def test_task_comments_author_and_owner_delete(client, alice, user_factory, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    task = client.post(f"{w}/tasks", headers=alice, json={"title": "Wybrać zespół"}).json()
    url = f"{w}/tasks/{task['id']}/comments"
    partner = user_factory("partner@example.com")
    invite_and_accept(client, alice, partner, wedding, "partner@example.com")
    viewer = user_factory("ogladam@example.com")
    invite_and_accept(client, alice, viewer, wedding, "ogladam@example.com", role="viewer")

    rows = client.post(url, headers=alice, json={"text": "Dzwoniłam do dwóch zespołów"}).json()
    rows = client.post(url, headers=partner, json={"text": "  Wolę ten z saksofonem  "}).json()
    assert [r["text"] for r in rows] == ["Dzwoniłam do dwóch zespołów", "Wolę ten z saksofonem"]
    mine = client.get(url, headers=partner).json()
    assert [r["mine"] for r in mine] == [False, True]
    assert client.get(url, headers=viewer).status_code == 200
    assert client.post(url, headers=viewer, json={"text": "X"}).status_code == 403
    # Partner nie usunie cudzego komentarza; właściciel usuwa każdy.
    r = client.delete(f"{url}/{rows[0]['id']}", headers=partner)
    assert (r.status_code, r.json()["code"]) == (403, "task_comment.forbidden")
    assert client.delete(f"{url}/{rows[1]['id']}", headers=alice).status_code == 204
    assert len(client.get(url, headers=alice).json()) == 1
    assert len(client.get(f"{w}/export", headers=alice).json()["task_comments"]) == 1
