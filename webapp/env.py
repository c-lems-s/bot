"""Environnement d'execution : local (Cloudflare) vs cloud (Railway, etc.)."""

from __future__ import annotations

import os


def app_env() -> str:
    """Retourne ``local`` ou ``cloud``.

    Priorite :
    1. ``APP_ENV`` explicite (local|dev|cloud|prod|railway…)
    2. Presence de variables Railway
    3. Defaut ``local``
    """
    raw = (os.getenv("APP_ENV") or "").strip().lower()
    if raw in ("local", "dev", "development"):
        return "local"
    if raw in ("cloud", "prod", "production", "railway"):
        return "cloud"
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"):
        return "cloud"
    return "local"


def is_cloud() -> bool:
    return app_env() == "cloud"


def is_local() -> bool:
    return not is_cloud()


def bind_host() -> str:
    """Host d'ecoute HTTP. Surcharge possible via ``BIND_HOST``."""
    override = (os.getenv("BIND_HOST") or "").strip()
    if override:
        return override
    return "0.0.0.0" if is_cloud() else "127.0.0.1"


def has_database_url() -> bool:
    return bool((os.getenv("DATABASE_URL") or "").strip())


def should_create_database() -> bool:
    """True seulement en local sans DATABASE_URL (Postgres admin local)."""
    if has_database_url():
        return False
    if is_cloud():
        return False
    flag = (os.getenv("CREATE_DATABASE") or "").strip().lower()
    if flag in ("0", "false", "no"):
        return False
    if flag in ("1", "true", "yes"):
        return True
    return True


def telegram_webhook_enabled() -> bool:
    return (os.getenv("TELEGRAM_WEBHOOK") or "").strip() in ("1", "true", "True")


def public_base_url() -> str:
    """URL HTTPS publique de la Mini App (PUBLIC_BASE_URL / WEBAPP_URL / Railway)."""
    for key in ("PUBLIC_BASE_URL", "WEBAPP_URL", "RAILWAY_PUBLIC_DOMAIN"):
        raw = (os.getenv(key) or "").strip().rstrip("/")
        if not raw:
            continue
        if key == "RAILWAY_PUBLIC_DOMAIN" and not raw.startswith("http"):
            return f"https://{raw}"
        return raw
    return ""
