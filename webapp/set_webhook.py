"""Enregistre / affiche le webhook Telegram pour le deploy cloud.

Usage :
    python -m webapp.set_webhook
    python -m webapp.set_webhook --url https://xxx.up.railway.app
    python -m webapp.set_webhook --info
    python -m webapp.set_webhook --delete

Variables :
    PUBLIC_BASE_URL   ex. https://bot-production-xxxx.up.railway.app
    TELEGRAM_BOT_TOKEN
    TELEGRAM_WEBHOOK_SECRET
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from webapp import telegram as tg  # noqa: E402


def _public_base() -> str:
    for key in ("PUBLIC_BASE_URL", "WEBAPP_URL", "RAILWAY_PUBLIC_DOMAIN"):
        raw = (os.getenv(key) or "").strip().rstrip("/")
        if not raw:
            continue
        if key == "RAILWAY_PUBLIC_DOMAIN" and not raw.startswith("http"):
            return f"https://{raw}"
        return raw
    return ""


def _webhook_url(base: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/telegram/webhook"):
        return base
    return f"{base}/telegram/webhook"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Webhook Telegram Bot API")
    parser.add_argument("--url", help="URL publique (https://…), sinon PUBLIC_BASE_URL")
    parser.add_argument("--info", action="store_true", help="Affiche getWebhookInfo")
    parser.add_argument("--delete", action="store_true", help="Supprime le webhook")
    parser.add_argument(
        "--keep-pending",
        action="store_true",
        help="Ne drop pas les updates en attente",
    )
    args = parser.parse_args(argv)

    if not tg.bot_token():
        print("[-] TELEGRAM_BOT_TOKEN manquant")
        return 1

    if args.info:
        info = tg.get_webhook_info()
        print(info or {"error": "echec getWebhookInfo"})
        return 0 if info is not None else 1

    if args.delete:
        ok = tg.delete_webhook(drop_pending_updates=not args.keep_pending)
        print(ok if ok is not None else {"error": "echec deleteWebhook"})
        return 0 if ok is not None else 1

    base = (args.url or _public_base()).strip()
    if not base:
        print("[-] URL manquante : --url ou PUBLIC_BASE_URL / WEBAPP_URL")
        return 1
    if not base.startswith("https://"):
        print("[-] L'URL webhook doit etre en https://")
        return 1

    secret = (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    if not secret:
        print("[!] TELEGRAM_WEBHOOK_SECRET vide — recommande en prod")

    hook = _webhook_url(base)
    print(f"[set_webhook] {hook}")
    result = tg.set_webhook(
        hook,
        secret_token=secret or None,
        drop_pending_updates=not args.keep_pending,
    )
    if not result:
        print("[-] setWebhook echoue (voir logs)")
        return 1
    print("[+] Webhook OK")
    info = tg.get_webhook_info()
    if info:
        print(f"    url={info.get('url')}")
        print(f"    pending={info.get('pending_update_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
