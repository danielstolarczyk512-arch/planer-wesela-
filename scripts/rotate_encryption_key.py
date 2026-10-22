"""Rotacja klucza szyfrowania danych wrażliwych (uwagi dietetyczne gości, sekrety MFA).

Procedura (szczegóły: docs/wdrozenie.md, sekcja „Rotacja klucza”):
1. `python -m scripts.rotate_encryption_key generate` → nowy klucz (wyświetlony raz).
2. Konfiguracja: WP_DATA_ENCRYPTION_KEY=<nowy>, WP_DATA_ENCRYPTION_KEY_VERSION=<poprzednia+1>,
   WP_DATA_ENCRYPTION_PREVIOUS_KEYS="<poprzednia>:<stary klucz>"; restart api i workera.
3. `python -m scripts.rotate_encryption_key rotate --dry-run`, potem bez --dry-run.
4. Gdy `old_key` = 0: usuń WP_DATA_ENCRYPTION_PREVIOUS_KEYS i zniszcz stary klucz.
"""

import sys

from app.core import crypto
from app.core.db import get_sessionmaker
from app.modules.guests import service as guests
from app.modules.identity import mfa


def main(argv: list[str]) -> int:
    if argv[:1] == ["generate"]:
        print(crypto.generate_key())
        return 0
    if argv[:1] != ["rotate"]:
        print(__doc__)
        return 2
    dry_run = "--dry-run" in argv
    with get_sessionmaker()() as db:
        stats = guests.reencrypt_notes(db, dry_run=dry_run)
        mfa_stats = mfa.reencrypt_secrets(db, dry_run=dry_run)
    mode = "podgląd" if dry_run else "wykonano"
    version = crypto.current_version()
    print(f"Rotacja ({mode}), bieżąca wersja klucza {version}: uwagi {stats}, MFA {mfa_stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
