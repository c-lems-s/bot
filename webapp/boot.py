"""Preparation runtime (DB) avant Flask / gunicorn.

Usage :
    python -m webapp.boot
"""

from __future__ import annotations

import os
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
    else:
        from db.connection import close_pool, init_db
        from db.migrate import migrate

        print("[boot] Mode cloud / DATABASE_URL — migrate uniquement")
        close_pool()
        init_db()
        migrate()

    _ensure_uploads()
    _maybe_seed_admin()
    _maybe_set_webhook()


def _ensure_uploads() -> None:
    from webapp.paths import ensure_uploads_dirs, uploads_root

    info = ensure_uploads_dirs()
    print(f"[boot] uploads root={uploads_root()} writable={info.get('writable')}")
    for err in info.get("errors") or []:
        print(f"[boot] uploads warn: {err}")


def _maybe_seed_admin() -> None:
    """Si ADMIN_TELEGRAM_ID est pose et config.admin vide → seed."""
    raw = (os.getenv("ADMIN_TELEGRAM_ID") or "").strip()
    if not raw:
        return
    try:
        from webapp.seed_admin_env import main as seed_main

        code = seed_main([])
        if code != 0:
            print("[boot] seed admin ignore / echec (non bloquant)")
    except Exception as e:
        print(f"[boot] seed admin ignore : {e}")


def _maybe_set_webhook() -> None:
    """Si SET_WEBHOOK_ON_BOOT=1 + PUBLIC_BASE_URL → enregistre le webhook."""
    flag = (os.getenv("SET_WEBHOOK_ON_BOOT") or "").strip().lower()
    if flag not in ("1", "true", "yes"):
        return
    try:
        from webapp.set_webhook import main as webhook_main

        code = webhook_main([])
        if code != 0:
            print("[boot] set_webhook ignore / echec (non bloquant)")
    except Exception as e:
        print(f"[boot] set_webhook ignore : {e}")


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
