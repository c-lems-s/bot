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
    """Poll Telegram seulement si webhook inactif / non enregistre."""
    from webapp.env import telegram_webhook_enabled
    from webapp import telegram as tg

    webhook_url = ""
    last_err = ""
    if telegram_webhook_enabled():
        try:
            info = tg.get_webhook_info() or {}
            webhook_url = (info.get("url") or "").strip()
            last_err = (info.get("last_error_message") or "").strip()
        except Exception as e:
            server.log.warning("getWebhookInfo echec : %s", e)

        if webhook_url:
            server.log.info(
                "TELEGRAM_WEBHOOK actif — poll non demarre (url=%s%s)",
                webhook_url,
                f" last_error={last_err}" if last_err else "",
            )
            if last_err:
                server.log.warning(
                    "Telegram signale une erreur webhook recente : %s "
                    "(verifiez TELEGRAM_WEBHOOK_SECRET / HTTPS / redeploy)",
                    last_err,
                )
            return

        server.log.warning(
            "TELEGRAM_WEBHOOK=1 mais webhook URL vide — "
            "fallback poll (process master) pour que /start reponde. "
            "Corrigez PUBLIC_BASE_URL + secret puis redeploy."
        )

    force = bool(telegram_webhook_enabled() and not webhook_url)
    # Mode poll volontaire : un seul worker evite les getUpdates en double.
    # Fallback webhook vide : le thread tourne dans le master (when_ready).
    if not force and workers != 1:
        server.log.warning(
            "Poll Telegram ignore (WEB_CONCURRENCY=%s > 1). "
            "Utilisez TELEGRAM_WEBHOOK=1 avec webhook enregistre, "
            "ou WEB_CONCURRENCY=1.",
            workers,
        )
        return

    try:
        from webapp.bot_poll import start_polling_thread

        if start_polling_thread(force=force):
            server.log.info(
                "Poll Telegram demarre (%s)",
                "fallback webhook vide / master" if force else "worker unique",
            )
    except Exception as e:
        server.log.warning("Poll Telegram ignore : %s", e)
