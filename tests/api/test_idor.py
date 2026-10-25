"""Izolacja wesel: osoba spoza wesela dostaje 404 na KAŻDYM endpoincie /weddings/{id}/…

Test sprawdza też, że każda trasa z {wedding_id} jest tu pokryta. Nowy endpoint bez testu
IDOR spowoduje błąd.
"""

import re

import pytest

from app.main import create_app

API = "/api/v1"
FAKE = "0192aaaa-0000-7000-8000-000000000000"
PLN = {"amount": "1.00", "currency": "PLN"}
MULTIPART = object()  # znacznik: żądanie z plikiem (multipart/form-data)

W = "/weddings/{w}"
CASES = [
    ("GET", W, None),
    ("PATCH", W, {"city": "X"}),
    ("DELETE", W, None),
    ("GET", f"{W}/summary", None),
    ("GET", f"{W}/export", None),
    ("GET", f"{W}/events", None),
    ("POST", f"{W}/events", {"kind": "other", "name": "X"}),
    ("GET", f"{W}/events/{{x}}", None),
    ("PATCH", f"{W}/events/{{x}}", {"name": "X"}),
    ("DELETE", f"{W}/events/{{x}}", None),
    ("GET", f"{W}/members", None),
    ("PATCH", f"{W}/members/{{x}}", {"role": "viewer"}),
    ("DELETE", f"{W}/members/{{x}}", None),
    ("GET", f"{W}/invitations", None),
    ("POST", f"{W}/invitations", {"email": "x@example.com"}),
    ("DELETE", f"{W}/invitations/{{x}}", None),
    # planer
    ("GET", f"{W}/tasks", None),
    ("POST", f"{W}/tasks", {"title": "X"}),
    ("GET", f"{W}/tasks/{{x}}", None),
    ("PATCH", f"{W}/tasks/{{x}}", {"title": "X"}),
    ("DELETE", f"{W}/tasks/{{x}}", None),
    ("POST", f"{W}/tasks/{{x}}/complete", None),
    ("POST", f"{W}/tasks/{{x}}/reopen", None),
    ("PUT", f"{W}/tasks/{{x}}/dependencies/{{x}}", None),
    ("DELETE", f"{W}/tasks/{{x}}/dependencies/{{x}}", None),
    ("POST", f"{W}/reschedule", {"planned_month": "2027-10"}),
    ("POST", f"{W}/tasks/catch-up", {"dry_run": True}),
    ("POST", f"{W}/tasks/sync-template", {"dry_run": True}),
    ("GET", f"{W}/vendor-checklist", None),
    ("POST", f"{W}/vendors/{{x}}/checklist/standard", {"kind": "question"}),
    ("POST", f"{W}/vendors/{{x}}/checklist", {"text": "X"}),
    ("PATCH", f"{W}/vendor-checklist/{{x}}", {"answer": "X"}),
    ("DELETE", f"{W}/vendor-checklist/{{x}}", None),
    ("GET", f"{W}/calendar?start=2027-01-01&end=2027-02-01", None),
    ("GET", f"{W}/calendar-feed", None),
    ("POST", f"{W}/calendar-feed", None),
    ("DELETE", f"{W}/calendar-feed", None),
    ("GET", f"{W}/vendors/{{x}}/day-link", None),
    ("POST", f"{W}/vendors/{{x}}/day-link", None),
    ("DELETE", f"{W}/vendors/{{x}}/day-link", None),
    ("GET", f"{W}/guest-info", None),
    ("PUT", f"{W}/guest-info", {"published": False}),
    ("GET", f"{W}/guest-info/preview", None),
    ("POST", f"{W}/rsvp-emails", {"dry_run": True}),
    ("GET", f"{W}/guests/export.csv", None),
    ("GET", f"{W}/budget/export.csv", None),
    ("POST", f"{W}/rsvp-qr", {"dry_run": True}),
    # dobór usługodawców i zapytania do firm (etapy 2-3 pakietu „agenci weselni”)
    ("GET", f"{W}/vendor-preferences/{{x}}", None),
    ("PUT", f"{W}/vendor-preferences/{{x}}", {"notes": "X"}),
    ("POST", f"{W}/vendor-search", {"category": "photographer"}),
    ("GET", f"{W}/candidates", None),
    ("POST", f"{W}/candidates", {"catalog_vendor_id": FAKE}),
    ("PATCH", f"{W}/candidates/{{x}}", {"state": "rejected"}),
    ("POST", f"{W}/candidates/{{x}}/to-vendor", None),
    ("GET", f"{W}/candidates-compare?ids={{x}}&ids={{x}}", None),
    ("GET", f"{W}/discovery-requests", None),
    ("POST", f"{W}/discovery-requests", {"category": "dj"}),
    ("GET", f"{W}/discovery-requests/{{x}}", None),
    ("GET", f"{W}/concierge/conversations", None),
    ("POST", f"{W}/concierge/conversations", None),
    ("GET", f"{W}/concierge/conversations/{{x}}/messages", None),
    ("POST", f"{W}/concierge/conversations/{{x}}/messages", {"text": "X"}),
    ("GET", f"{W}/inquiries", None),
    ("POST", f"{W}/inquiries", {"recipients": [{"catalog_vendor_id": FAKE}]}),
    ("GET", f"{W}/inquiries/{{x}}", None),
    (
        "PUT",
        f"{W}/inquiries/{{x}}",
        {"base_revision": 1, "to_email": "x@example.com", "subject": "X", "body": "X"},
    ),
    ("DELETE", f"{W}/inquiries/{{x}}", None),
    (
        "POST",
        f"{W}/inquiries/{{x}}/approve-and-send",
        {
            "revision_id": FAKE,
            "content_hash": "0" * 64,
            "to_email": "x@example.com",
        },
    ),
    (
        "POST",
        f"{W}/inquiries-approve-and-send",
        {
            "items": [
                [
                    FAKE,
                    {
                        "revision_id": FAKE,
                        "content_hash": "0" * 64,
                        "to_email": "x@example.com",
                    },
                ]
            ]
        },
    ),
    ("POST", f"{W}/inquiries/{{x}}/import-response", {"text": "X"}),
    ("POST", f"{W}/inquiries/{{x}}/responses/{{x}}/analyze", None),
    # budżet
    ("GET", f"{W}/budget/categories", None),
    ("POST", f"{W}/budget/categories", {"name": "X"}),
    ("PATCH", f"{W}/budget/categories/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/budget/categories/{{x}}", None),
    ("POST", f"{W}/budget/apply-split", {"dry_run": True}),
    ("GET", f"{W}/budget/items", None),
    ("POST", f"{W}/budget/items", {"category_id": FAKE, "name": "X", "planned": PLN}),
    ("GET", f"{W}/budget/items/{{x}}", None),
    ("PATCH", f"{W}/budget/items/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/budget/items/{{x}}", None),
    ("GET", f"{W}/budget/items/{{x}}/payments", None),
    ("POST", f"{W}/budget/items/{{x}}/payments", {"kind": "other", "amount": PLN}),
    ("PATCH", f"{W}/payments/{{x}}", {"notes": "x"}),
    ("DELETE", f"{W}/payments/{{x}}", None),
    ("POST", f"{W}/payments/{{x}}/mark-paid", {}),
    ("GET", f"{W}/payments/schedule", None),
    ("GET", f"{W}/budget/overview", None),
    ("GET", f"{W}/budget/history", None),
    # goście
    ("GET", f"{W}/households", None),
    ("POST", f"{W}/households", {"name": "X"}),
    ("GET", f"{W}/households/{{x}}", None),
    ("PATCH", f"{W}/households/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/households/{{x}}", None),
    ("POST", f"{W}/households/{{x}}/rsvp-link", None),
    ("DELETE", f"{W}/households/{{x}}/rsvp-link", None),
    ("POST", f"{W}/households/{{x}}/guests", {"first_name": "X"}),
    ("GET", f"{W}/guests", None),
    ("PATCH", f"{W}/guests/{{x}}", {"first_name": "Y"}),
    ("DELETE", f"{W}/guests/{{x}}", None),
    ("PUT", f"{W}/guests/{{x}}/attendance/{{x}}", {"status": "attending"}),
    ("GET", f"{W}/guests/stats", None),
    ("GET", f"{W}/attendance-forecast", None),
    ("GET", f"{W}/attention", None),
    ("GET", f"{W}/after-wedding", None),
    ("POST", f"{W}/deliverables", {"title": "X"}),
    ("PATCH", f"{W}/deliverables/{{x}}", {"title": "Y"}),
    ("DELETE", f"{W}/deliverables/{{x}}", None),
    ("PUT", f"{W}/after-checks/{{x}}", {"done": True}),
    ("GET", f"{W}/logistics", None),
    ("GET", f"{W}/day-transport", None),
    ("GET", f"{W}/day-checklist", None),
    ("POST", f"{W}/day-checklist", {"title": "X"}),
    ("POST", f"{W}/day-checklist/typical", None),
    ("PATCH", f"{W}/day-checklist/{{x}}", {"title": "Y"}),
    ("DELETE", f"{W}/day-checklist/{{x}}", None),
    ("PUT", f"{W}/day-checklist/{{x}}/done", {"done": True}),
    ("GET", f"{W}/music", None),
    ("POST", f"{W}/music", {"moment": "must", "title": "X"}),
    ("PUT", f"{W}/music/song-requests", {"enabled": True}),
    ("PATCH", f"{W}/music/{{x}}", {"title": "Y"}),
    ("DELETE", f"{W}/music/{{x}}", None),
    ("GET", f"{W}/photo-groups", None),
    ("POST", f"{W}/photo-groups", {"title": "X"}),
    ("POST", f"{W}/photo-groups/typical", None),
    ("PATCH", f"{W}/photo-groups/{{x}}", {"title": "Y"}),
    ("POST", f"{W}/photo-groups/{{x}}/move", {"direction": "up"}),
    ("DELETE", f"{W}/photo-groups/{{x}}", None),
    ("PUT", f"{W}/photo-groups/{{x}}/done", {"done": True}),
    ("GET", f"{W}/prep", None),
    ("PUT", f"{W}/prep", {"hair_artists": 2}),
    ("POST", f"{W}/prep/people", {"name": "X"}),
    ("PATCH", f"{W}/prep/people/{{x}}", {"name": "Y"}),
    ("POST", f"{W}/prep/people/{{x}}/move", {"direction": "up"}),
    ("DELETE", f"{W}/prep/people/{{x}}", None),
    ("GET", f"{W}/menu", None),
    ("POST", f"{W}/menu", {"course": "main", "name": "X"}),
    ("PUT", f"{W}/menu/show", {"enabled": True}),
    ("PATCH", f"{W}/menu/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/menu/{{x}}", None),
    ("GET", f"{W}/guest-page", None),
    ("PUT", f"{W}/guest-page", {"show_tables": True}),
    ("PUT", f"{W}/guest-page/announcement", {"text": "X"}),
    ("POST", f"{W}/guest-page/announcement/email", {"dry_run": True}),
    ("GET", f"{W}/wishes", None),
    ("PUT", f"{W}/wishes/{{x}}/hidden", {"hidden": True}),
    ("DELETE", f"{W}/wishes/{{x}}", None),
    ("GET", f"{W}/helpers", None),
    ("POST", f"{W}/helpers", {"name": "X"}),
    ("POST", f"{W}/helpers/{{x}}/link", None),
    ("DELETE", f"{W}/helpers/{{x}}", None),
    ("PUT", f"{W}/tasks/{{x}}/helper", {"helper_id": None}),
    ("GET", f"{W}/budget/cashflow", None),
    ("GET", f"{W}/budget/guest-cost", None),
    ("GET", f"{W}/search", None),
    ("GET", f"{W}/gifts", None),
    ("POST", f"{W}/gifts", {"title": "X"}),
    ("PATCH", f"{W}/gifts/{{x}}", {"title": "Y"}),
    ("DELETE", f"{W}/gifts/{{x}}", None),
    ("GET", f"{W}/tasks/{{x}}/comments", None),
    ("POST", f"{W}/tasks/{{x}}/comments", {"text": "X"}),
    ("DELETE", f"{W}/tasks/{{x}}/comments/{{x}}", None),
    ("POST", f"{W}/transport-runs", {"name": "X", "capacity": 1}),
    ("PATCH", f"{W}/transport-runs/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/transport-runs/{{x}}", None),
    ("PUT", f"{W}/transport-runs/{{x}}/guests", {"guest_ids": []}),
    ("POST", f"{W}/lodging-rooms", {"place": "X", "name": "1", "beds": 1}),
    ("PATCH", f"{W}/lodging-rooms/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/lodging-rooms/{{x}}", None),
    ("PUT", f"{W}/lodging-rooms/{{x}}/guests", {"guest_ids": []}),
    ("GET", f"{W}/lodging/rooming.csv", None),
    ("GET", f"{W}/invitation-delivery", None),
    ("POST", f"{W}/invitation-delivery/plan", {"household_ids": [FAKE]}),
    ("POST", f"{W}/invitation-delivery/delivered", {"household_ids": [FAKE]}),
    ("GET", f"{W}/budget/indexation", None),
    ("PUT", f"{W}/budget/indexation/assumptions", {"expected_rate": 0.05, "worst_rate": 0.1}),
    ("GET", f"{W}/ceremony-documents", None),
    ("PUT", f"{W}/ceremony-documents/{{x}}", {}),
    ("GET", f"{W}/funders", None),
    ("POST", f"{W}/funders", {"name": "X"}),
    ("GET", f"{W}/funders/{{x}}", None),
    ("PATCH", f"{W}/funders/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/funders/{{x}}", None),
    ("POST", f"{W}/funders/{{x}}/contributions", {"amount": PLN}),
    ("DELETE", f"{W}/funders/{{x}}/contributions/{{x}}", None),
    ("GET", f"{W}/my-contribution", None),
    ("POST", f"{W}/my-contribution/reports", {"amount": PLN}),
    ("POST", f"{W}/funders/{{x}}/contributions/{{x}}/confirm", None),
    ("GET", f"{W}/vendors/{{x}}/brief", None),
    ("PUT", f"{W}/vendors/{{x}}/brief", {}),
    ("GET", f"{W}/vendor-briefs", None),
    ("GET", f"{W}/reserve", None),
    ("POST", f"{W}/reserve", {"name": "X"}),
    ("PATCH", f"{W}/reserve/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/reserve/{{x}}", None),
    ("POST", f"{W}/reserve/{{x}}/invite", {"guests": [{"first_name": "X"}]}),
    ("POST", f"{W}/guests/import", {"csv": "household;first_name\nA;B"}),
    # usługodawcy
    ("GET", f"{W}/vendors", None),
    ("POST", f"{W}/vendors", {"name": "X"}),
    ("GET", f"{W}/vendors/{{x}}", None),
    ("PATCH", f"{W}/vendors/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/vendors/{{x}}", None),
    # oferty
    ("GET", f"{W}/offers", None),
    ("POST", f"{W}/offers", {"vendor_id": FAKE, "title": "X"}),
    ("GET", f"{W}/offers/{{x}}", None),
    ("PATCH", f"{W}/offers/{{x}}", {"title": "Y"}),
    ("DELETE", f"{W}/offers/{{x}}", None),
    ("POST", f"{W}/offers/{{x}}/approve", {}),
    ("POST", f"{W}/offers/{{x}}/reject", None),
    ("POST", f"{W}/offers/{{x}}/select", {}),
    ("POST", f"{W}/offers/compare", {"offer_ids": [FAKE]}),
    (
        "POST",
        f"{W}/offers/scenarios",
        {"offer_ids": [FAKE], "scenarios": [{"label": "A"}, {"label": "B"}]},
    ),
    # dokumenty
    ("GET", f"{W}/documents", None),
    ("GET", f"{W}/documents/search?q=ab", None),
    ("POST", f"{W}/documents", MULTIPART),
    ("GET", f"{W}/documents/{{x}}", None),
    ("PATCH", f"{W}/documents/{{x}}", {"title": "Y"}),
    ("DELETE", f"{W}/documents/{{x}}", None),
    ("POST", f"{W}/documents/{{x}}/versions", MULTIPART),
    ("GET", f"{W}/documents/{{x}}/versions/{{x}}/file", None),
    ("GET", f"{W}/documents/{{x}}/versions/{{x}}/text", None),
    ("POST", f"{W}/documents/{{x}}/versions/{{x}}/retry", None),
    # AI
    ("POST", f"{W}/documents/{{x}}/versions/{{x}}/analyze", {"vendor_id": FAKE}),
    ("GET", f"{W}/ai-runs", None),
    ("GET", f"{W}/ai-runs/{{x}}", None),
    # harmonogram dnia
    ("GET", f"{W}/schedule", None),
    ("POST", f"{W}/schedule", {"title": "X", "starts_at": "2027-08-21T12:00:00+02:00"}),
    ("GET", f"{W}/schedule/conflicts", None),
    ("POST", f"{W}/schedule/shift", {"from_item_id": FAKE, "minutes": 10}),
    ("POST", f"{W}/schedule/from-template", {"ceremony_time": "15:00"}),
    ("GET", f"{W}/schedule/{{x}}", None),
    ("PATCH", f"{W}/schedule/{{x}}", {"title": "Y"}),
    ("DELETE", f"{W}/schedule/{{x}}", None),
    ("PUT", f"{W}/schedule/{{x}}/dependencies/{{x}}", None),
    ("DELETE", f"{W}/schedule/{{x}}/dependencies/{{x}}", None),
    # plan stołów
    ("GET", f"{W}/seating", None),
    ("POST", f"{W}/seating/auto", {}),
    ("POST", f"{W}/seating/auto-runs", {}),
    ("GET", f"{W}/seating/auto-runs/{{x}}", None),
    ("PUT", f"{W}/seating/assignments", {"assignments": []}),
    ("POST", f"{W}/seating/clear", {}),
    ("GET", f"{W}/seating/room", None),
    ("PUT", f"{W}/seating/room", {"width_m": 20, "length_m": 12}),
    ("POST", f"{W}/seating/seat-numbers", {}),
    ("PUT", f"{W}/seating/guests/{{x}}", {"table_id": FAKE}),
    ("DELETE", f"{W}/seating/guests/{{x}}", None),
    ("GET", f"{W}/seating/tables", None),
    ("POST", f"{W}/seating/tables", {"name": "X", "capacity": 8}),
    ("GET", f"{W}/seating/tables/{{x}}", None),
    ("PATCH", f"{W}/seating/tables/{{x}}", {"name": "Y"}),
    ("DELETE", f"{W}/seating/tables/{{x}}", None),
    ("GET", f"{W}/seating/rules", None),
    ("POST", f"{W}/seating/rules", {"kind": "apart", "guest_a_id": FAKE, "guest_b_id": FAKE}),
    ("DELETE", f"{W}/seating/rules/{{x}}", None),
]


def send(client, method, url, body, headers=None):
    if body is MULTIPART:
        return client.request(
            method,
            url,
            headers=headers,
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
    return client.request(method, url, headers=headers, json=body)


def test_all_wedding_routes_are_covered():
    routes = {
        (
            method.upper(),
            re.sub(r"\{(?!wedding_id)[a-z_]+\}", "{x}", path.removeprefix(API)).replace(
                "{wedding_id}", "{w}"
            ),
        )
        for path, operations in create_app().openapi()["paths"].items()
        if "{wedding_id}" in path
        for method in operations
    }
    covered = {(m, p.split("?")[0]) for m, p, _ in CASES}  # parametry zapytania poza ścieżką
    assert routes == covered, f"Brak testu IDOR: {routes - covered}; nadmiar: {covered - routes}"


@pytest.mark.parametrize(("method", "path", "body"), CASES)
def test_outsider_gets_404(client, alice, user_factory, wedding, method, path, body):
    outsider = user_factory("obcy@example.com")
    url = API + path.format(w=wedding["id"], x=FAKE)
    r = send(client, method, url, body, headers={**outsider, "If-Match": '"1"'})
    assert r.status_code == 404, f"{method} {path}: {r.status_code} {r.text}"
    assert client.get(f"{API}/weddings/{wedding['id']}", headers=alice).status_code == 200


@pytest.mark.parametrize(("method", "path", "body"), CASES)
def test_anonymous_gets_401(client, wedding, method, path, body):
    url = API + path.format(w=wedding["id"], x=FAKE)
    assert send(client, method, url, body).status_code == 401
