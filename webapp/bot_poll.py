"""Polling Telegram (commandes bot /start, /actif).

Lance en thread daemon depuis webapp.server, ou :
    python -m webapp.bot_poll
"""

from __future__ import annotations

import logging
import threading
import time

from webapp import bot_actif
from webapp import bot_start
from webapp import telegram as tg

log = logging.getLogger(__name__)

_started = False
_offset: int | None = None


def process_update(update: dict) -> None:
    try:
        if bot_start.process_update(update):
            log.info("Update consomme par /start")
            return
        if bot_actif.process_update(update):
            log.info("Update consomme par /actif")
            return
        msg = update.get("message") or update.get("edited_message") or {}
        text = (msg.get("text") or "").strip()
        if text.startswith("/"):
            log.info("Commande ignoree (non geree) : %r", text[:80])
    except Exception:
        log.exception("Erreur process_update")
        raise


def _poll_loop() -> None:
    global _offset
    log.info("Telegram bot poll demarre (/start, /actif)")
    while True:
        try:
            updates = tg.get_updates(offset=_offset, timeout=25)
            for upd in updates:
                uid = upd.get("update_id")
                if uid is not None:
                    _offset = int(uid) + 1
                process_update(upd)
        except Exception:
            log.exception("Erreur poll Telegram")
            time.sleep(3)


def start_polling_thread(*, force: bool = False) -> bool:
    """Demarre le poll si TELEGRAM_BOT_TOKEN present. Idempotent.

    ``force=True`` : demarre meme si TELEGRAM_WEBHOOK=1 (fallback si webhook vide).
    """
    global _started
    if _started:
        return True
    if not tg.bot_token():
        log.warning("TELEGRAM_BOT_TOKEN absent — poll bot desactive")
        return False
    from webapp.env import telegram_webhook_enabled

    # Desactive si webhook explicite (sauf fallback force)
    if telegram_webhook_enabled() and not force:
        log.info("TELEGRAM_WEBHOOK=1 — poll desactive (utilisez /telegram/webhook)")
        return False
    _started = True
    t = threading.Thread(target=_poll_loop, name="tg-bot-poll", daemon=True)
    t.start()
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not start_polling_thread():
        raise SystemExit(1)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
