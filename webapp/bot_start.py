"""Commande Telegram /start — bienvenue + bouton Mini App boutique."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from webapp import telegram as tg
from webapp.env import public_base_url

log = logging.getLogger(__name__)

WELCOME_TEXT = (
    "Bienvenue !\n\n"
    "Ouvrez la boutique pour commander depuis Telegram."
)
BUTTON_LABEL = "Accéder à la boutique"


def _shop_keyboard(url: str) -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": BUTTON_LABEL,
                    "web_app": {"url": url},
                }
            ]
        ]
    }


def send_start(chat_id: int, *, url: Optional[str] = None) -> None:
    """Envoie le message de bienvenue (+ bouton web_app si URL connue)."""
    base = (url or public_base_url() or "").strip().rstrip("/")
    if base.startswith("https://"):
        result = tg.send_message(
            int(chat_id),
            WELCOME_TEXT,
            reply_markup=_shop_keyboard(base),
        )
        if result is None:
            log.error("/start sendMessage echoue (chat_id=%s url=%s)", chat_id, base)
        else:
            log.info("/start envoye (chat_id=%s)", chat_id)
        return
    # Sans URL publique : message seul (évite bouton cassé)
    log.warning("/start sans PUBLIC_BASE_URL — bouton boutique omis")
    result = tg.send_message(
        int(chat_id),
        WELCOME_TEXT
        + "\n\n<i>Boutique momentanément indisponible (URL non configuree).</i>",
    )
    if result is None:
        log.error("/start sendMessage echoue (chat_id=%s, sans URL)", chat_id)


def handle_start_command(message: Dict[str, Any]) -> bool:
    """Traite /start. Retourne True si consomme."""
    text = (message.get("text") or "").strip()
    if not text.startswith("/start"):
        return False
    cmd = text.split()[0].split("@")[0]
    if cmd != "/start":
        return False

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return True

    send_start(int(chat_id))
    return True


def process_update(update: Dict[str, Any]) -> bool:
    """Traite update /start. True si consomme."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return False
    return handle_start_command(msg)
