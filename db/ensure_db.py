"""Cree la base kfc_perso si absente (local), puis applique les migrations."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

os.environ.setdefault("PGCLIENTENCODING", "UTF8")


def _create_database_if_needed() -> None:
    """Cree la DB locale en se connectant a la base ``postgres``.

    Ignore si ``DATABASE_URL`` / cloud (base deja provisionnee).
    """
    from webapp.env import should_create_database

    if not should_create_database():
        print("[ensure_db] Creation DB ignoree (DATABASE_URL ou APP_ENV=cloud)")
        return

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "root")
    dbname = os.getenv("DB_NAME", "kfc_perso")

    conn = psycopg2.connect(
        host=host, port=port, dbname="postgres", user=user, password=password
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
    if cur.fetchone() is None:
        cur.execute(f'CREATE DATABASE "{dbname}"')
        print(f"[+] Base creee : {dbname}")
    cur.close()
    conn.close()


def ensure_database() -> None:
    """Cree la base si besoin (local), applique les migrations, seeds legacy."""
    _create_database_if_needed()

    from db.connection import close_pool, init_db
    from db.migrate import migrate

    close_pool()
    init_db()
    migrate()

    try:
        from db.import_legacy import import_blacklist_json

        n = import_blacklist_json()
        if n:
            print(f"[+] Blacklist JSON importee : {n} resto(s)")
    except Exception as e:
        print(f"[!] Import blacklist JSON ignore : {e}")

    try:
        from db.seed_config import seed_config_from_file

        seed_config_from_file()
    except Exception as e:
        print(f"[!] Import config.json → table config ignore : {e}")


def main():
    ensure_database()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[-] {e}")
        sys.exit(1)
