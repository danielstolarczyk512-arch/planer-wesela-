"""Kontrola środowiska produkcyjnego/stagingu za Caddy (deploy/compose.prod.yaml).

Użycie: uv run python -m scripts.staging_check https://localhost:9443 [--insecure]
--insecure tylko dla lokalnego stagingu (certyfikat wewnętrzny Caddy dla localhost).
Tworzy fikcyjne konto testowe i usuwa je na końcu.
"""

import sys
import time
import uuid

import httpx

from tests.fixtures.offer_corpus import corpus

OK = True


def check(label: str, condition: bool, detail: object = "") -> None:
    global OK
    OK &= condition
    print(f"[{'OK ' if condition else 'BŁĄD'}] {label} {detail if not condition else ''}")


def main(base: str, insecure: bool) -> None:
    c = httpx.Client(base_url=base, verify=not insecure, timeout=30)
    r = c.get("/health/ready")
    check("HTTPS + health/ready", r.status_code == 200 and r.json()["status"] == "ok", r.text)
    h = r.headers
    check("HSTS", "max-age=31536000" in h.get("strict-transport-security", ""), dict(h))
    check("nagłówki bezpieczeństwa", h.get("x-frame-options") == "DENY" and "server" not in h)
    check("dokumentacja API wyłączona (prod)", c.get("/api/v1/docs").status_code == 404)
    http = base.replace("https://", "http://").replace(":9443", ":9080")
    redirect = httpx.get(f"{http}/health/live", follow_redirects=False, timeout=10)
    check("HTTP → HTTPS", redirect.status_code in (301, 308), redirect.status_code)

    email = f"staging-{uuid.uuid4().hex[:8]}@example.com"
    password = f"Staging-{uuid.uuid4().hex}"
    reg = c.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "accept_terms": True, "accept_privacy": True},
    )
    check("rejestracja", reg.status_code in (201, 202), reg.text[:200])
    login = c.post("/api/v1/auth/login", json={"email": email, "password": password})
    check("logowanie", login.status_code == 200, login.text[:200])
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    w = c.post("/api/v1/weddings", headers=auth, json={"name": "Staging"}).json()
    sample = next(s for s in corpus() if s.mime == "application/pdf" and not s.needs_ocr)
    up = c.post(
        f"/api/v1/weddings/{w['id']}/documents",
        headers=auth,
        files={"file": ("oferta.pdf", sample.data, "application/pdf")},
        data={"kind": "offer"},
    )
    check("upload (zapis do wolumenu przy read-only FS)", up.status_code == 202, up.text[:200])
    doc = up.json()
    status = "pending"
    for _ in range(30):
        status = c.get(f"/api/v1/weddings/{w['id']}/documents/{doc['id']}", headers=auth).json()[
            "versions"
        ][-1]["text_status"]
        if status in ("done", "failed"):
            break
        time.sleep(1)
    check("worker: ekstrakcja tekstu", status == "done", status)
    c.delete(f"/api/v1/weddings/{w['id']}", headers=auth)
    gone = c.request("DELETE", "/api/v1/me", headers=auth, json={"password": password})
    check("usunięcie konta testowego", gone.status_code == 202, gone.text[:200])
    print("Wszystkie kontrole przeszły." if OK else "SĄ BŁĘDY.")
    sys.exit(0 if OK else 1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "https://localhost:9443", "--insecure" in sys.argv)
