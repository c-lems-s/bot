"""Smoke test post-deploy (local ou Railway).

Usage :
    python -m webapp.smoke_deploy
    python -m webapp.smoke_deploy --base https://xxx.up.railway.app
    PUBLIC_BASE_URL=https://… python -m webapp.smoke_deploy --deep
"""

from __future__ import annotations

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def _base_url(cli: str | None) -> str:
    if cli:
        return cli.rstrip("/")
    for key in ("PUBLIC_BASE_URL", "WEBAPP_URL", "SMOKE_BASE_URL"):
        raw = (os.getenv(key) or "").strip().rstrip("/")
        if raw:
            return raw
    return "http://127.0.0.1:8080"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test deploy")
    parser.add_argument("--base", help="URL de base (defaut PUBLIC_BASE_URL ou localhost)")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Appelle /health?deep=1 (DB + uploads)",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)

    base = _base_url(args.base)
    path = "/health?deep=1" if args.deep else "/health"
    url = f"{base}{path}"
    print(f"[smoke] GET {url}")

    try:
        r = requests.get(url, timeout=args.timeout)
    except Exception as e:
        print(f"[-] Connexion impossible : {e}")
        return 1

    print(f"[smoke] status={r.status_code}")
    try:
        data = r.json()
    except Exception:
        print(f"[-] Corps non JSON : {r.text[:200]}")
        return 1
    print(f"[smoke] body={data}")

    if r.status_code != 200 or not data.get("ok"):
        print("[-] Health KO")
        return 1

    # Page d'accueil (static)
    try:
        home = requests.get(f"{base}/", timeout=args.timeout)
        print(f"[smoke] GET / → {home.status_code}")
        if home.status_code != 200:
            print("[-] Index KO")
            return 1
    except Exception as e:
        print(f"[-] Index impossible : {e}")
        return 1

    # Webhook info (optionnel, si token present)
    if (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip():
        try:
            from webapp import telegram as tg

            info = tg.get_webhook_info()
            if info is not None:
                print(
                    f"[smoke] webhook url={info.get('url')!r} "
                    f"pending={info.get('pending_update_count')}"
                )
            else:
                print("[smoke] webhook info indisponible")
        except Exception as e:
            print(f"[smoke] webhook info ignore : {e}")

    print("[+] Smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
