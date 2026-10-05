"""Preparation runtime (DB) avant Flask / gunicorn.

Usage :
    python -m webapp.boot
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

from webapp.env import app_env, has_database_url, is_cloud, should_create_database  # noqa: E402

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def prepare_runtime() -> None:
    """Migrations (+ creation DB locale si besoin). Idempotent."""
    print(f"[boot] APP_ENV={app_env()}")
    _log_db_config()
    _assert_cloud_db_ready()

    if should_create_database():
        from db.ensure_db import ensure_database

        print("[boot] Mode local — ensure_database (create + migrate)")
        ensure_database()
    else:
        from db.connection import close_pool, init_db
        from db.migrate import migrate

        if has_database_url():
            print("[boot] Migrate via DATABASE_URL")
        else:
            print("[boot] Migrate via DB_HOST/DB_*")
        close_pool()
        init_db()
        migrate()

    _ensure_uploads()
    _maybe_seed_admin()
    _maybe_set_bot_commands()
    _ensure_telegram_ingress()


def _database_url_host() -> str | None:
    """Host extrait de DATABASE_URL (sans secrets), ou None si absent/invalide."""
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return None
    try:
        # postgres://user:pass@host:port/db — urlparse gère aussi postgresql://
        parsed = urlparse(raw)
        if parsed.hostname:
            return parsed.hostname
        # Fallback si URL non standard
        after_at = raw.split("@", 1)[1] if "@" in raw else raw
        hostport = after_at.split("/", 1)[0]
        return hostport.split(":")[0] or None
    except Exception:
        return None


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    h = host.strip().lower().strip("[]")
    return h in _LOOPBACK_HOSTS or h.startswith("127.")


def _assert_cloud_db_ready() -> None:
    """En cloud, refuse le demarrage sans DATABASE_URL Postgres distant."""
    if not is_cloud():
        return

    if not has_database_url():
        raise RuntimeError(
            "DATABASE_URL manquant en cloud. "
            "Sur Railway : ajoutez Postgres, puis Variables → "
            "Add Variable Reference → Postgres → DATABASE_URL "
            "(ou collez ${{Postgres.DATABASE_URL}}). "
            "Sans ça le boot tombe sur localhost:5432."
        )

    host = _database_url_host()
    if _is_loopback_host(host):
        raise RuntimeError(
            f"DATABASE_URL pointe vers {host!r} (loopback) en cloud. "
            "Ce n'est pas la base Railway. "
            "Variables → Add Variable Reference → Postgres.DATABASE_URL, "
            "puis redeploy."
        )


def _log_db_config() -> None:
    """Log non sensible de la config DB (aide debug Railway)."""
    if has_database_url():
        host = _database_url_host() or "?"
        print(f"[boot] DATABASE_URL present (host={host})")
        if is_cloud() and _is_loopback_host(host):
            print("[boot] ATTENTION: host loopback en cloud — connexion impossible")
    else:
        db_host = os.getenv("DB_HOST", "localhost")
        print(
            "[boot] DATABASE_URL absent — "
            f"fallback DB_HOST={db_host!r}"
        )
        if is_cloud():
            print(
                "[boot] ATTENTION cloud: sans DATABASE_URL → "
                "Connection refused sur localhost:5432"
            )


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


def _maybe_set_bot_commands() -> None:
    """Enregistre le menu /start (public) et /actif (admin only)."""
    try:
        from webapp.bot_commands import sync_bot_commands

        if sync_bot_commands():
            print("[boot] Menu commandes Telegram OK (/start public, /actif admin)")
        else:
            print("[boot] Menu commandes ignore / echec (non bloquant)")
    except Exception as e:
        print(f"[boot] Menu commandes ignore : {e}")


def _ensure_telegram_ingress() -> None:
    """Webhook si TELEGRAM_WEBHOOK=1, sinon nettoie pour le poll.

    Avant, le poll etait coupe sans setWebhook → /start muet.
    """
    try:
        from webapp.telegram_ingress import ensure_telegram_ingress

        info = ensure_telegram_ingress()
        mode = info.get("mode")
        detail = info.get("detail") or ""
        if info.get("ok"):
            print(f"[boot] Telegram ingress OK ({mode}) — {detail}")
        else:
            print(f"[boot] Telegram ingress KO ({mode}) — {detail}")
            print(
                "    → Sans ingress, /start et /actif ne repondent pas. "
                "Verifiez PUBLIC_BASE_URL + TELEGRAM_WEBHOOK_SECRET "
                "ou desactivez TELEGRAM_WEBHOOK pour le poll."
            )
    except Exception as e:
        print(f"[boot] Telegram ingress ignore : {e}")


def main() -> None:
    try:
        prepare_runtime()
    except Exception as e:
        print(f"[-] Boot DB impossible : {e}")
        if is_cloud():
            print("    Cause frequente : Postgres non lie au service web.")
            print("    Railway → service web → Variables → Add Variable Reference")
            print("    → choisissez le service Postgres → DATABASE_URL")
            print("    Puis Redeploy (Settings → Redeploy).")
            if not has_database_url():
                print("    (DATABASE_URL est actuellement VIDE dans ce container)")
            else:
                host = _database_url_host()
                if _is_loopback_host(host):
                    print(f"    (DATABASE_URL pointe vers {host!r} — incorrect en cloud)")
        else:
            print("    Verifiez .env puis : python -m db.ensure_db")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
