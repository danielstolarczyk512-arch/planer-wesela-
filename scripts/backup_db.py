"""Kopia zapasowa bazy (pg_dump) z weryfikacją odtworzenia i opcjonalną kopią na NAS.

Użycie:
  uv run python -m scripts.backup_db backup   # zrzut + weryfikacja + kopia na NAS + rotacja
  uv run python -m scripts.backup_db verify PLIK  # próbne odtworzenie do bazy tymczasowej
  uv run python -m scripts.backup_db drill   # pełna próba: kopia → pusta baza + pliki → porównanie

Konfiguracja (.env):
  BACKUP_DIR=backups                     katalog lokalny (w .gitignore)
  BACKUP_TARGET=\\\\DS225\\backup\\wedding  opcjonalnie: udział SMB na Synology
  BACKUP_KEEP=14                         ile najnowszych kopii trzymać

Klucz WP_DATA_ENCRYPTION_KEY NIE trafia do kopii bazy: przechowuj go osobno (menedżer haseł),
bez niego zaszyfrowane kolumny są nie do odczytania.
"""

import os
import shutil

# Wywołania wyłącznie docker compose ze stałą listą argumentów, bez powłoki.
import subprocess  # nosec B404
import sys
import tarfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER = os.environ.get("POSTGRES_USER", "wedding")
DB = os.environ.get("POSTGRES_DB", "wedding")
CHECK_DB = "wedding_restore_check"


def _compose(*args: str, stdin: bytes | None = None, service: str = "db") -> bytes:
    cmd = ["docker", "compose", "exec", "-T", service, *args]
    result = subprocess.run(  # noqa: S603  # nosec B603
        cmd, cwd=ROOT, input=stdin, capture_output=True, check=False
    )
    if result.returncode != 0:
        sys.exit(f"Błąd: {' '.join(args[:2])}: {result.stderr.decode(errors='replace')[:500]}")
    return result.stdout


def backup() -> Path:
    target_dir = ROOT / os.environ.get("BACKUP_DIR", "backups")
    target_dir.mkdir(exist_ok=True)
    stamp = f"{datetime.now().astimezone():%Y%m%d-%H%M%S}"
    path = target_dir / f"{DB}-{stamp}.dump"
    path.write_bytes(_compose("pg_dump", "-U", USER, "-d", DB, "-Fc", "--no-owner"))
    print(f"Zrzut: {path} ({path.stat().st_size / 1024:.0f} KiB)")
    verify(path)
    files = target_dir / f"{DB}-files-{stamp}.tar.gz"
    files.write_bytes(_compose("tar", "-czf", "-", "-C", "/app", "storage", service="api"))
    with tarfile.open(files) as archive:  # weryfikacja: archiwum da się odczytać
        count = sum(1 for m in archive.getmembers() if m.isfile())
    print(f"Pliki dokumentów: {files} ({count} plików)")
    nas = os.environ.get("BACKUP_TARGET")
    if nas:
        for item in (path, files):
            shutil.copy2(item, Path(nas) / item.name)
        print(f"Skopiowano na NAS: {nas}")
    keep = int(os.environ.get("BACKUP_KEEP", "14"))
    rotate(target_dir, keep, f"{DB}-2*.dump")
    rotate(target_dir, keep, f"{DB}-files-*.tar.gz")
    return path


def verify(path: Path) -> None:
    """Odtwarza zrzut do tymczasowej bazy i sprawdza, że tabele istnieją."""
    _compose("dropdb", "-U", USER, "--if-exists", CHECK_DB)
    _compose("createdb", "-U", USER, CHECK_DB)
    try:
        _compose("pg_restore", "-U", USER, "-d", CHECK_DB, "--no-owner", stdin=path.read_bytes())
        out = _compose(
            "psql",
            "-U",
            USER,
            "-d",
            CHECK_DB,
            "-tAc",
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'",
        )
        tables = int(out.decode().strip() or 0)
        if tables < 10:
            sys.exit(f"Weryfikacja nieudana: odtworzono tylko {tables} tabel.")
        print(f"Weryfikacja OK: odtworzono {tables} tabel.")
    finally:
        _compose("dropdb", "-U", USER, "--if-exists", CHECK_DB)


DRILL_DB = "wedding_restore_drill"
DRILL_TABLES = (
    "users",
    "weddings",
    "tasks",
    "budget_items",
    "payments",
    "guests",
    "vendors",
    "offers",
    "document_versions",
    "schedule_items",
    "seat_assignments",
    "audit_log",
)


def _count(db: str, table: str) -> int:
    # Nazwa tabeli wyłącznie ze stałej listy DRILL_TABLES.
    query = f"SELECT count(*) FROM {table}"  # noqa: S608  # nosec B608
    out = _compose("psql", "-U", USER, "-d", db, "-tAc", query)
    return int(out.decode().strip() or 0)


def drill() -> None:
    """Próba odtworzenia od zera: świeża kopia → nowa, pusta baza + pliki → porównanie.

    Nie dotyka bazy produkcyjnej ani plików aplikacji (wszystko w osobnej bazie i katalogu).
    """
    dump = backup()
    files = sorted(dump.parent.glob(f"{DB}-files-*.tar.gz"))[-1]
    _compose("dropdb", "-U", USER, "--if-exists", DRILL_DB)
    _compose("createdb", "-U", USER, DRILL_DB)
    try:
        _compose("pg_restore", "-U", USER, "-d", DRILL_DB, "--no-owner", stdin=dump.read_bytes())
        head = _compose(
            "psql", "-U", USER, "-d", DRILL_DB, "-tAc", "SELECT version_num FROM alembic_version"
        )
        print(f"Wersja schematu po odtworzeniu: {head.decode().strip()}")
        diffs = []
        for table in DRILL_TABLES:
            src, dst = _count(DB, table), _count(DRILL_DB, table)
            print(f"  {table:<20} źródło {src:>7}  odtworzone {dst:>7}")
            if src != dst:
                diffs.append(table)
        keys = set(
            _compose(
                "psql",
                "-U",
                USER,
                "-d",
                DRILL_DB,
                "-tAc",
                "SELECT DISTINCT storage_key FROM document_versions",
            )
            .decode()
            .split()
        )
        with tarfile.open(files) as archive:
            archived = {m.name.removeprefix("storage/") for m in archive.getmembers() if m.isfile()}
        missing = keys - archived
        print(f"Pliki: {len(keys)} w bazie, {len(archived)} w archiwum, brakujących {len(missing)}")
        if diffs or missing:
            sys.exit(f"Próba NIEUDANA: różnice w {diffs}, brakujące pliki: {len(missing)}")
        print("Próba odtworzenia od zera: OK.")
    finally:
        _compose("dropdb", "-U", USER, "--if-exists", DRILL_DB)


def rotate(directory: Path, keep: int, pattern: str) -> None:
    dumps = sorted(directory.glob(pattern), reverse=True)
    for old in dumps[keep:]:
        old.unlink()
        print(f"Usunięto starą kopię: {old.name}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "backup"
    if command == "backup":
        backup()
    elif command == "verify" and len(sys.argv) > 2:
        verify(Path(sys.argv[2]))
    elif command == "drill":
        drill()
    else:
        sys.exit(__doc__)
