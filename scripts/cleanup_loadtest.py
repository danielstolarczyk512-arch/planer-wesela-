"""Usuwa wesela z testów obciążeniowych („Obciążenie N”) przez API — tylko z kont loadtest-*.

Uruchomienie (API dev na 127.0.0.1:8010):
    uv run python -m scripts.cleanup_loadtest            # podgląd
    uv run python -m scripts.cleanup_loadtest --delete   # usunięcie

Usuwa wyłącznie wesela, w których kontem jest `loadtest-N@example.com` i których nazwa zaczyna się
od „Obciążenie ” — inne wesela (także na tych kontach) zostają. Hasło kont: jak w scripts/seed.py.

Konta testu obciążenia (po potwierdzeniu właściciela, z kopią bazy):
    uv run python -m scripts.cleanup_loadtest --accounts           # podgląd
    uv run python -m scripts.cleanup_loadtest --accounts --delete  # usunięcie
Każde konto `loadtest-N@example.com` bez wesel: żądanie usunięcia przez API (jak w aplikacji),
potem natychmiastowa anonimizacja tylko tych kont (bez czekania na karencję). Inne konta
oczekujące na usunięcie nie są ruszane. Wymaga dostępu do bazy (WP_DATABASE_URL jak dla API).
"""

import os
import sys

import httpx

API = os.environ.get("WP_API_URL", "http://127.0.0.1:8010/api/v1")
PASSWORD = os.environ.get("WP_SEED_PASSWORD", "Demo-Wesele-2027!")  # gitleaks:allow
PREFIX = "Obciążenie "


def main(delete: bool) -> None:
    found = removed = 0
    with httpx.Client(base_url=API, timeout=30) as client:
        for n in range(50):
            email = f"loadtest-{n}@example.com"
            r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
            if r.status_code != 200:
                continue
            headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            weddings = client.get("/weddings", headers=headers, params={"limit": 100}).json()
            items = weddings["items"] if isinstance(weddings, dict) else weddings
            for w in items:
                if not w["name"].startswith(PREFIX):
                    continue
                found += 1
                if delete:
                    d = client.delete(f"/weddings/{w['id']}", headers=headers)
                    if d.status_code == 204:
                        removed += 1
                    else:
                        print(f"Nie usunięto {w['name']}: {d.status_code} {d.text[:120]}")
    print(f"Wesel z testu obciążenia: {found}; usunięto: {removed}")


def accounts(delete: bool) -> None:
    from sqlalchemy import select

    from app.core.db import get_sessionmaker
    from app.modules.identity.models import User
    from app.modules.identity.service import anonymize_user

    requested = skipped = 0
    with httpx.Client(base_url=API, timeout=30) as client:
        for n in range(50):
            email = f"loadtest-{n}@example.com"
            r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
            if r.status_code != 200:
                continue
            headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
            weddings = client.get("/weddings", headers=headers, params={"limit": 100}).json()
            items = weddings["items"] if isinstance(weddings, dict) else weddings
            if items:  # konto z weselem zostaje
                skipped += 1
                print(f"Pominięto {email}: ma wesela ({len(items)})")
                continue
            requested += 1
            if delete:
                d = client.request("DELETE", "/me", headers=headers, json={"password": PASSWORD})
                if d.status_code != 202:
                    print(f"Nie zgłoszono usunięcia {email}: {d.status_code} {d.text[:120]}")
    anonymized = 0
    if delete:
        with get_sessionmaker()() as db:
            users = db.scalars(
                select(User).where(
                    User.status == "pending_deletion", User.email.like("loadtest-%@example.com")
                )
            ).all()
            for user in users:
                anonymize_user(db, user)
            db.commit()
            anonymized = len(users)
    print(f"Konta do usunięcia: {requested}; pominięte: {skipped}; zanonimizowane: {anonymized}")


if __name__ == "__main__":
    if "--accounts" in sys.argv:
        accounts("--delete" in sys.argv)
    else:
        main("--delete" in sys.argv)
