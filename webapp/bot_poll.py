"""Polling Telegram (commandes bot /actif).

Lance en thread daemon depuis webapp.server, ou :
    python -m webapp.bot_poll
"""

from __future__ import annotations

import logging
import os
import threading
import time

from webapp import telegram as tg
from webapp import bot_actif

log = logging.getLogger(__name__)

_started = False
_offset: int | None = None


def process_update(update: dict) -> None:
    bot_actif.process_update(update)


def _poll_loop() -> None:
    global _offset
    log.info("Telegram bot poll demarre (/actif)")
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


def start_polling_thread() -> bool:
    """Demarre le poll si TELEGRAM_BOT_TOKEN present. Idempotent."""
    global _started
    if _started:
        return True
    if not tg.bot_token():
        log.warning("TELEGRAM_BOT_TOKEN absent — poll bot desactive")
        return False
    from webapp.env import telegram_webhook_enabled

    # Desactive si webhook explicite
    if telegram_webhook_enabled():
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
