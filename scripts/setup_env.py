"""Tworzy lub uzupełnia .env: losowe WP_JWT_SECRET i WP_DATA_ENCRYPTION_KEY.

Istniejące wartości nigdy nie są nadpisywane (zmiana klucza szyfrowania = utrata danych).
"""

import base64
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env_file = ROOT / ".env"

GENERATED = {
    "WP_JWT_SECRET": lambda: secrets.token_urlsafe(48),
    "WP_DATA_ENCRYPTION_KEY": lambda: base64.urlsafe_b64encode(os.urandom(32)).decode(),
}

source = env_file if env_file.exists() else ROOT / ".env.example"
lines = source.read_text(encoding="utf-8").splitlines()
present = {line.split("=", 1)[0] for line in lines if "=" in line}
changed: list[str] = []

for i, line in enumerate(lines):
    key, _, value = line.partition("=")
    if key in GENERATED and (not value or "change-me" in value):
        lines[i] = f"{key}={GENERATED[key]()}"
        changed.append(key)
for key, make in GENERATED.items():
    if key not in present:
        lines.append(f"{key}={make()}")
        changed.append(key)

if changed or not env_file.exists():
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f".env: wygenerowano {', '.join(changed)}" if changed else ".env: bez zmian.")
