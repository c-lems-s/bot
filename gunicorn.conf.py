"""Config gunicorn — cloud (Railway, etc.)."""

from __future__ import annotations

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
capture_output = True
# Prefork : un seul process parent charge le code
preload_app = True


def when_ready(server):
    """Poll Telegram seulement si webhook desactive (dev cloud / fallback)."""
    from webapp.env import telegram_webhook_enabled

    if telegram_webhook_enabled():
        server.log.info("TELEGRAM_WEBHOOK actif — poll non demarre")
        return
    if workers != 1:
        server.log.warning(
            "Poll Telegram ignore (WEB_CONCURRENCY=%s > 1). "
            "Utilisez TELEGRAM_WEBHOOK=1 en cloud, ou WEB_CONCURRENCY=1.",
            workers,
        )
        return
    try:
        from webapp.bot_poll import start_polling_thread

        if start_polling_thread():
            server.log.info("Poll Telegram demarre (worker unique)")
    except Exception as e:
        server.log.warning("Poll Telegram ignore : %s", e)
