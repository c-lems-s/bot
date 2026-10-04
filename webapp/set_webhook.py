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
from webapp.env import public_base_url  # noqa: E402
from webapp.telegram_ingress import (  # noqa: E402
    ensure_webhook,
    webhook_endpoint_url,
    webhook_info,
)


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
        info = webhook_info()
        print(info or {"error": "echec getWebhookInfo"})
        return 0 if info is not None else 1

    if args.delete:
        ok = tg.delete_webhook(drop_pending_updates=not args.keep_pending)
        print(ok if ok is not None else {"error": "echec deleteWebhook"})
        return 0 if ok is not None else 1

    if args.url:
        # Surcharge temporaire de l'URL publique pour ce run
        os.environ["PUBLIC_BASE_URL"] = args.url.strip()

    base = public_base_url()
    if not base:
        print(
            "[-] URL manquante : PUBLIC_BASE_URL, WEBAPP_URL ou RAILWAY_PUBLIC_DOMAIN. "
            "Railway → service web → Settings → Networking → Generate Domain, "
            "puis Variables : PUBLIC_BASE_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}"
        )
        return 1

    print(f"[set_webhook] {webhook_endpoint_url(base)}")
    ok, detail = ensure_webhook(drop_pending=not args.keep_pending)
    if not ok:
        print(f"[-] {detail}")
        return 1
    print(f"[+] Webhook OK — {detail}")
    info = webhook_info()
    if info:
        print(f"    pending={info.get('pending_update_count')}")
        if info.get("last_error_message"):
            print(f"    last_error={info.get('last_error_message')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
