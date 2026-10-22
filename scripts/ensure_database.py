"""Tworzy bazę z WP_DATABASE_URL, jeśli jej nie ma (np. osobna baza testów E2E `wedding_e2e`).

Uruchamiane przez kontener `migrate-e2e` przed migracjami. Łączy się z bazą `postgres` na tym samym
serwerze. Nic nie usuwa.
"""

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def main() -> None:
    url = make_url(get_settings().database_url)
    name = url.database
    if not name:
        raise SystemExit("WP_DATABASE_URL nie zawiera nazwy bazy.")
    admin = url.set(drivername="postgresql", database="postgres")
    conninfo = admin.render_as_string(hide_password=False)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if exists:
            print(f"Baza {name} już istnieje.")
            return
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        print(f"Utworzono bazę {name}.")


if __name__ == "__main__":
    main()
