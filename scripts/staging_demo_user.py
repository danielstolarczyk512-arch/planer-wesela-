"""Fikcyjne konto testowe na stagingu (WP_ENV=prod blokuje scripts/seed.py).

Uruchamiane w kontenerze stagingu (tam nie ma katalogu scripts/), z katalogu deploy/:
  Get-Content ../scripts/staging_demo_user.py -Raw |
    docker compose -f compose.prod.yaml --env-file .env.prod exec -T api python -
Hasło z WP_STAGING_DEMO_PASSWORD (domyślne jak w scripts/seed.py). Nigdy na produkcji z danymi.
"""

import os

from sqlalchemy import select

import app.models  # noqa: F401  # rejestracja wszystkich modeli
from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.core.security import hash_password
from app.modules.identity.models import Consent, User

EMAIL = "demo@example.com"
PASSWORD = os.environ.get("WP_STAGING_DEMO_PASSWORD", "Demo-Wesele-2027!")  # gitleaks:allow

settings = get_settings()
with get_sessionmaker()() as db:
    if db.scalars(select(User).where(User.email == EMAIL)).first():
        print("Konto testowe już istnieje.")
    else:
        user = User(
            email=EMAIL,
            password_hash=hash_password(PASSWORD),
            display_name="Konto testowe stagingu",
            email_verified_at=utcnow(),
        )
        db.add(user)
        db.flush()
        db.add(Consent(user_id=user.id, type="terms", document_version=settings.terms_version))
        db.add(Consent(user_id=user.id, type="privacy", document_version=settings.privacy_version))
        db.commit()
        print("Utworzono konto testowe stagingu.")
