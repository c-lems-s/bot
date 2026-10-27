"""Assure que le bot recoit les updates (webhook cloud ou poll).

Probleme frequent :
  TELEGRAM_WEBHOOK=1 desactive le poll, mais setWebhook n'a jamais ete appele
  → /start et /actif restent muets.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from webapp import telegram as tg
from webapp.env import public_base_url, telegram_webhook_enabled

log = logging.getLogger(__name__)


def webhook_endpoint_url(base: Optional[str] = None) -> str:
    raw = (base or public_base_url() or "").strip().rstrip("/")
    if not raw:
        return ""
    if raw.endswith("/telegram/webhook"):
        return raw
    return f"{raw}/telegram/webhook"


def webhook_info() -> Optional[Dict[str, Any]]:
    return tg.get_webhook_info()


def ensure_webhook(*, drop_pending: bool = True) -> Tuple[bool, str]:
    """Enregistre le webhook Bot API. Retourne (ok, detail)."""
    if not tg.bot_token():
        return False, "TELEGRAM_BOT_TOKEN manquant"

    hook = webhook_endpoint_url()
    if not hook.startswith("https://"):
        return (
            False,
            "PUBLIC_BASE_URL manquant/invalide — "
            "Railway → Networking → Generate Domain puis "
            "PUBLIC_BASE_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}",
        )

    secret = (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    if not secret:
        return (
            False,
            "TELEGRAM_WEBHOOK_SECRET manquant — obligatoire pour /telegram/webhook",
        )

    result = tg.set_webhook(
        hook,
        secret_token=secret,
        drop_pending_updates=drop_pending,
    )
    if not result:
        return False, f"setWebhook echoue pour {hook}"

    info = webhook_info() or {}
    url = (info.get("url") or "").strip()
    err = (info.get("last_error_message") or "").strip()
    detail = f"url={url or hook}"
    if err:
        detail += f" last_error={err}"
    if url and url.rstrip("/") != hook.rstrip("/"):
        return False, f"webhook enregistre mais URL inattendue ({detail})"
    return True, detail


def ensure_telegram_ingress() -> Dict[str, Any]:
    """Au boot : si mode webhook, enregistre/verifie le webhook.

    Retourne un resume pour les logs boot.
    """
    summary: Dict[str, Any] = {
        "mode": "webhook" if telegram_webhook_enabled() else "poll",
        "ok": False,
        "detail": "",
    }

    if not tg.bot_token():
        summary["detail"] = "TELEGRAM_BOT_TOKEN manquant"
        return summary

    if not telegram_webhook_enabled():
        # Mode poll : s'assurer qu'aucun vieux webhook ne bloque getUpdates
        info = webhook_info() or {}
        if (info.get("url") or "").strip():
            tg.delete_webhook(drop_pending_updates=False)
            summary["detail"] = "ancien webhook supprime (mode poll)"
        else:
            summary["detail"] = "mode poll (pas de webhook)"
        summary["ok"] = True
        return summary

    # Mode webhook : toujours (re)enregistrer si possible
    force = (os.getenv("SET_WEBHOOK_ON_BOOT") or "").strip().lower()
    # TELEGRAM_WEBHOOK=1 implique set au boot ; SET_WEBHOOK_ON_BOOT=0 pour skip
    if force in ("0", "false", "no"):
        info = webhook_info() or {}
        url = (info.get("url") or "").strip()
        summary["ok"] = bool(url)
        summary["detail"] = (
            f"SET_WEBHOOK_ON_BOOT=0 — webhook actuel={url or '(vide)'}"
        )
        if info.get("last_error_message"):
            summary["detail"] += f" last_error={info.get('last_error_message')}"
        return summary

    ok, detail = ensure_webhook(drop_pending=True)
    summary["ok"] = ok
    summary["detail"] = detail
    if not ok:
        log.error("Ingress Telegram KO : %s", detail)
    else:
        log.info("Ingress Telegram OK : %s", detail)
    return summary
