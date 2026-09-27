"""
Auth Telegram WebApp (initData).

Valide la signature HMAC et upsert l'utilisateur.

Dev local (hors Telegram) uniquement si :
  - ALLOW_DEV_AUTH=1
  - ET TELEGRAM_BOT_TOKEN est vide

Des qu'un token bot est configure, seuls les initData signes sont acceptes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from functools import wraps
from typing import Any, Callable, Dict
from urllib.parse import parse_qsl

from flask import jsonify, request

from db.repositories import users as users_repo


def _bot_token() -> str:
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def _max_age_seconds() -> int:
    try:
        return max(60, int(os.getenv("TELEGRAM_AUTH_MAX_AGE_SECONDS", "86400")))
    except ValueError:
        return 86400


def _dev_auth_enabled() -> bool:
    """True seulement en local explicite, sans token bot (sinon auth Telegram obligatoire)."""
    flag = (os.getenv("ALLOW_DEV_AUTH") or "").strip() in ("1", "true", "True", "yes")
    if not flag:
        return False
    if _bot_token():
        # Evite une prod ouverte par erreur (ALLOW_DEV_AUTH=1 + token renseigne).
        return False
    return True


def validate_webapp_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """Valide initData. Raises ValueError si invalide. Retourne le user Telegram."""
    if not init_data or not bot_token:
        raise ValueError("initData ou bot token manquant")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("hash manquant")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise ValueError("signature initData invalide")

    auth_date = parsed.get("auth_date")
    if auth_date:
        try:
            age = int(time.time()) - int(auth_date)
            if age > _max_age_seconds():
                raise ValueError("initData expire")
        except ValueError as e:
            if "expire" in str(e):
                raise
            raise ValueError("auth_date invalide") from e

    user_raw = parsed.get("user")
    if not user_raw:
        raise ValueError("user manquant dans initData")
    user = json.loads(user_raw)
    if not user.get("id"):
        raise ValueError("telegram user id manquant")
    return user


def resolve_request_user() -> Dict[str, Any]:
    """Resolut l'utilisateur courant. Raises PermissionError / ValueError."""
    init_data = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    bot_token = _bot_token()

    if init_data:
        if not bot_token:
            raise PermissionError("TELEGRAM_BOT_TOKEN manquant — auth Telegram impossible")
        tg_user = validate_webapp_init_data(init_data, bot_token)
        return users_repo.upsert_from_telegram(
            telegram_id=int(tg_user["id"]),
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
            language_code=tg_user.get("language_code"),
            initial_balance=0.0,
        )

    if _dev_auth_enabled():
        raw = request.headers.get("X-Dev-Telegram-Id") or "1"
        try:
            tid = int(raw)
        except ValueError:
            tid = 1
        return users_repo.upsert_from_telegram(
            telegram_id=tid,
            username="dev",
            first_name="Dev",
            last_name="User",
            language_code="fr",
            initial_balance=0.0,
        )

    raise PermissionError("Authentification Telegram requise")


def require_telegram_user(view: Callable):
    """Decorator Flask : place g.user ou renvoie 401."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        from flask import g

        try:
            g.user = resolve_request_user()
        except PermissionError as e:
            return jsonify({"error": str(e)}), 401
        except ValueError as e:
            return jsonify({"error": f"Auth invalide : {e}"}), 401
        except Exception as e:
            return jsonify({"error": f"Auth echouee : {e}"}), 401
        return view(*args, **kwargs)

    return wrapped
