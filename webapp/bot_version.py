"""Commande Telegram /version — admin uniquement (silencieux sinon)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from kfc.config import is_admin
from webapp import telegram as tg
from webapp.app_version import APP_VERSION

log = logging.getLogger(__name__)


def handle_version_command(message: Dict[str, Any]) -> bool:
    """Traite /version. Retourne True si consomme (meme si silencieux)."""
    text = (message.get("text") or "").strip()
    if not text.startswith("/version"):
        return False
    cmd = text.split()[0].split("@")[0]
    if cmd != "/version":
        return False

    from_user = message.get("from") or {}
    tid = from_user.get("id")
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    # Non-admin : ne repond rien (commande consommee, invisible menu public).
    if not is_admin(tid):
        log.info("/version ignore (non-admin tid=%s)", tid)
        return True

    if chat_id is None:
        return True

    tg.send_message(
        int(chat_id),
        f"<b>Version</b> : <code>{APP_VERSION}</code>",
    )
    return True


def process_update(update: Dict[str, Any]) -> bool:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return False
    return handle_version_command(msg)
