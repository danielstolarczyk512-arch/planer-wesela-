"""Test dymny end-to-end na działającym środowisku (task up). Tworzy fikcyjne dane demo.

Użycie: uv run python -m scripts.smoke_e2e [BASE_URL]   (domyślnie http://127.0.0.1:8010)
Wymaga konta demo (task seed). Kończy się kodem 1 przy pierwszym niepowodzeniu.
"""

import sys
import time
import uuid
from typing import Any

import httpx

from scripts.seed import DEMO_EMAIL, DEMO_PASSWORD

_ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (_ARGS[0] if _ARGS else "http://127.0.0.1:8010").rstrip("/")
API = f"{BASE}/api/v1"


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"[{'OK ' if condition else 'BŁĄD'}] {label} {detail}")
    if not condition:
        sys.exit(1)


def main() -> None:
    c = httpx.Client(timeout=15)
    check("health/ready", c.get(f"{BASE}/health/ready").json().get("status") == "ok")
    r = c.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    check("logowanie demo", r.status_code == 200, r.status_code)
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    w = c.post(
        f"{API}/weddings",
        headers=h,
        json={
            "name": f"Smoke {uuid.uuid4().hex[:6]}",
            "planned_month": "2027-09",
            "ceremony_type": "civil",
            "guest_count_planned": 80,
            "total_budget": {"amount": "60000", "currency": "PLN"},
        },
    ).json()
    url = f"{API}/weddings/{w['id']}"
    tasks = c.get(f"{url}/tasks", headers=h, params={"limit": 200}).json()["items"]
    check("zadania z szablonu", len(tasks) > 20, len(tasks))
    cats = c.get(f"{url}/budget/categories", headers=h).json()
    check("kategorie budżetu", len(cats) == 12, len(cats))

    ev = c.post(f"{url}/events", headers=h, json={"kind": "reception", "name": "Przyjęcie"}).json()
    hh = c.post(
        f"{url}/households",
        headers=h,
        json={"name": "Rodzina Testowa", "rsvp_deadline": "2027-08-01"},
    ).json()
    g = c.post(
        f"{url}/households/{hh['id']}/guests",
        headers=h,
        json={"first_name": "Jan", "dietary_note": "orzechy"},
    ).json()
    link = c.post(f"{url}/households/{hh['id']}/rsvp-link", headers=h).json()
    view = c.get(f"{API}/rsvp/{link['token']}").json()
    check("RSVP: podgląd bez logowania", len(view["guests"]) == 1)
    r = c.put(
        f"{API}/rsvp/{link['token']}",
        json={"responses": [{"guest_id": g["id"], "event_id": ev["id"], "status": "attending"}]},
    )
    check("RSVP: odpowiedź gościa", r.status_code == 200, r.status_code)

    s = c.get(f"{url}/summary", headers=h).json()
    check("pulpit: potwierdzeni", s["guests"]["confirmed"] == 1, s["guests"])

    item = c.post(
        f"{url}/budget/items",
        headers=h,
        json={
            "category_id": cats[0]["id"],
            "name": "Menu",
            "cost_mode": "per_guest",
            "unit_price": {"amount": "300", "currency": "PLN"},
            "guest_basis": "confirmed",
        },
    ).json()
    check(
        "koszt za osobę x potwierdzeni", item["estimated"]["amount"] == "300.00", item["estimated"]
    )

    ik = {**h, "Idempotency-Key": f"smoke-{uuid.uuid4().hex}"}
    a = c.post(f"{url}/tasks", headers=ik, json={"title": "Idempotencja"})
    b = c.post(f"{url}/tasks", headers=ik, json={"title": "Idempotencja"})
    check(
        "Idempotency-Key: powtórka bez duplikatu",
        a.json()["id"] == b.json()["id"] and b.headers.get("idempotency-replayed") == "true",
    )

    export = c.get(f"{url}/export", headers=h).json()
    check("eksport RODO zawiera gości", export["guests"][0]["dietary_note"] == "orzechy")

    # Harmonogram dnia i plan stołów (OR-Tools w obrazie produkcyjnym).
    plan = c.post(
        f"{url}/schedule/from-template",
        headers=h,
        json={"day": "2027-09-18", "ceremony_time": "14:00", "dry_run": False},
    )
    check(
        "harmonogram z szablonu", plan.status_code == 200 and plan.json()["items"], plan.text[:200]
    )
    c.post(f"{url}/seating/tables", headers=h, json={"name": "Stół 1", "capacity": 8})
    auto = c.post(f"{url}/seating/auto", headers=h, json={"dry_run": False}, timeout=60)
    seated = c.get(f"{url}/seating", headers=h).json()["stats"]["seated"]
    check(
        "plan stołów: automatyczne usadzenie",
        auto.status_code == 200 and seated == 1,
        auto.text[:200],
    )

    # Worker: e-mail z zaproszeniem trafia do Mailpit (do 20 s).
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    me = c.get(f"{API}/me", headers=h).json()
    if me["email_verified"]:
        c.post(f"{url}/invitations", headers=h, json={"email": email})
        found = False
        for _ in range(20):
            msgs = c.get(f"{BASE.rsplit(':', 1)[0]}:8025/api/v1/messages").json()["messages"]
            found = any(m["To"][0]["Address"] == email for m in msgs)
            if found:
                break
            time.sleep(1)
        check("worker: e-mail zaproszenia w Mailpit", found)

    documents_and_offers(c, h, url)
    c.delete(url, headers=h)
    print("Wszystkie kontrole przeszły.")


def _wait_text(c: httpx.Client, h: dict[str, str], doc_url: str) -> dict[str, Any]:
    for _ in range(60):
        version = c.get(doc_url, headers=h).json()["versions"][-1]
        if version["text_status"] in ("done", "failed"):
            return dict(version)
        time.sleep(1)
    return dict(version)


def documents_and_offers(c: httpx.Client, h: dict[str, str], url: str) -> None:
    from tests.fixtures.offer_corpus import corpus  # korpus syntetycznych ofert (dev)

    pdf = next(s for s in corpus() if s.mime == "application/pdf" and not s.needs_ocr)
    scan = next(s for s in corpus() if s.needs_ocr and s.mime == "image/png")
    va = c.post(f"{url}/vendors", headers=h, json={"name": "Sala A", "category": "venue"}).json()
    vb = c.post(f"{url}/vendors", headers=h, json={"name": "Sala B", "category": "venue"}).json()

    doc = c.post(
        f"{url}/documents",
        headers=h,
        data={"kind": "offer", "vendor_id": va["id"]},
        files={"file": ("oferta.pdf", pdf.data)},
    ).json()
    v = _wait_text(c, h, f"{url}/documents/{doc['id']}")
    check("dokument PDF: tekst wyodrębniony przez workera", v["text_status"] == "done", v)

    scan_doc = c.post(
        f"{url}/documents",
        headers=h,
        data={"kind": "offer"},
        files={"file": ("skan.png", scan.data)},
    ).json()
    sv = _wait_text(c, h, f"{url}/documents/{scan_doc['id']}")
    check("skan: OCR Tesseract w workerze", sv["text_status"] == "done" and sv["ocr_used"], sv)
    text = c.get(f"{url}/documents/{scan_doc['id']}/versions/{sv['id']}/text", headers=h).json()
    check("skan: rozpoznana kwota zadatku", scan.expected[2] in text["pages"][0]["text"])

    a = c.post(
        f"{url}/offers",
        headers=h,
        json={
            "vendor_id": va["id"],
            "title": "Pakiet A",
            "min_guests": 80,
            "source_document_version_id": v["id"],
            "components": [
                {
                    "label": "Menu",
                    "kind": "per_guest",
                    "amount": "330",
                    "citation": {"page": 1, "quote": "330 zł za osobę dorosłą"},
                }
            ],
            "terms": [
                {
                    "term_type": "deposit",
                    "amount": {"amount": "5000", "currency": "PLN"},
                    "deposit_kind": "deposit_zadatek",
                }
            ],
        },
    )
    check("oferta z cytatem z dokumentu", a.status_code == 201, a.text[:200])
    b = c.post(
        f"{url}/offers",
        headers=h,
        json={
            "vendor_id": vb["id"],
            "title": "Pakiet B",
            "components": [
                {"label": "Menu", "kind": "per_guest", "amount": "300"},
                {"label": "Obsługa", "kind": "percent", "amount": "10"},
            ],
        },
    ).json()
    cmp = c.post(
        f"{url}/offers/compare",
        headers=h,
        json={"offer_ids": [a.json()["id"], b["id"]], "adults": 100},
    ).json()
    totals = {r["title"]: r["total"]["amount"] for r in cmp["results"]}
    check(
        "porównanie ofert (100 os.)",
        totals == {"Pakiet A": "33000.00", "Pakiet B": "33000.00"},
        totals,
    )
    sel = c.post(f"{url}/offers/{a.json()['id']}/select", headers=h, json={}).json()
    check("wybór oferty → budżet + zadatek", sel.get("payments_created") == 1, sel)

    if "--ai" in sys.argv:
        ai_step(c, h, url, doc["id"], v["id"], vb["id"])


def ai_step(
    c: httpx.Client, h: dict[str, str], url: str, document_id: str, version_id: str, vendor_id: str
) -> None:
    """AI na prawdziwym modelu (Ollama na hoście, worker w Dockerze). Do 15 minut."""
    r = c.post(
        f"{url}/documents/{document_id}/versions/{version_id}/analyze",
        headers=h,
        json={"vendor_id": vendor_id},
    )
    check("AI: analiza zlecona", r.status_code == 202, r.text[:200])
    run_url = f"{url}/ai-runs/{r.json()['id']}"
    run: dict[str, Any] = {}
    for _ in range(900):
        run = c.get(run_url, headers=h).json()
        if run["status"] in ("succeeded", "failed", "blocked"):
            break
        time.sleep(1)
    check(
        "AI: lokalny model zakończył analizę",
        run.get("status") == "succeeded",
        {k: run.get(k) for k in ("status", "error", "model", "duration_ms")},
    )
    offer = c.get(f"{url}/offers/{run['offer_id']}", headers=h).json()
    menu = [x for x in offer["components"] if x["amount"] == "330.00"]
    check(
        "AI: szkic oferty z ceną 330 zł i cytatem",
        bool(menu) and menu[0]["citation"],
        {"status": offer["status"], "validation": run["validation"]},
    )
    check("AI: szkic czeka na przegląd", offer["status"] == "needs_review")


if __name__ == "__main__":
    main()
