"""Preparation runtime (DB) avant Flask / gunicorn.

Usage :
    python -m webapp.boot
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()

from webapp.env import app_env, is_cloud, should_create_database  # noqa: E402


def prepare_runtime() -> None:
    """Migrations (+ creation DB locale si besoin). Idempotent."""
    print(f"[boot] APP_ENV={app_env()}")
    if should_create_database():
        from db.ensure_db import ensure_database

        print("[boot] Mode local — ensure_database (create + migrate)")
        ensure_database()
        return

    from db.connection import close_pool, init_db
    from db.migrate import migrate

    print("[boot] Mode cloud / DATABASE_URL — migrate uniquement")
    close_pool()
    init_db()
    migrate()


def main() -> None:
    try:
        prepare_runtime()
    except Exception as e:
        print(f"[-] Boot DB impossible : {e}")
        if is_cloud():
            print("    Verifiez DATABASE_URL et que la base Railway est provisionnee.")
        else:
            print("    Verifiez .env puis : python -m db.ensure_db")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
