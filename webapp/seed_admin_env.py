"""Pose config.admin depuis ADMIN_TELEGRAM_ID (premier deploy cloud).

Usage :
    ADMIN_TELEGRAM_ID=123456789 python -m webapp.seed_admin_env
    ADMIN_TELEGRAM_ID=123456789 python -m webapp.seed_admin_env --force
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ecrase config.admin meme s'il est deja renseigne",
    )
    args = parser.parse_args(argv)

    raw = (os.getenv("ADMIN_TELEGRAM_ID") or "").strip()
    if not raw:
        print("[-] ADMIN_TELEGRAM_ID manquant")
        return 1
    try:
        admin_id = int(raw)
    except ValueError:
        print("[-] ADMIN_TELEGRAM_ID invalide")
        return 1

    from db.connection import init_db
    from db.repositories import config as config_repo
    from kfc.config import clear_cache

    init_db()
    row = config_repo.get()
    if not row:
        print("[-] Table config vide — lancez d'abord les migrations / seed_config")
        return 1

    current = row.get("admin")
    if current and not args.force:
        print(f"[seed_admin] admin deja = {current} (passez --force pour ecraser)")
        return 0

    updated = config_repo.upsert(
        account_id=row.get("account_id") or "",
        authorization=row.get("authorization") or row.get("auth_token") or "",
        cookies=row.get("cookies") or {},
        recaptcha_token=row.get("recaptcha_token") or "",
        enable_analytics=bool(row.get("enable_analytics", False)),
        balance=float(row.get("balance") or 0),
        currency=row.get("currency") or "EUR",
        reduction=float(row.get("reduction") if row.get("reduction") is not None else 100),
        version=str(row.get("version") or "1"),
        admin=admin_id,
        actif=bool(row.get("actif", True)),
        prochaine_heure=row.get("prochaine_heure"),
    )
    clear_cache()
    print(f"[+] config.admin = {updated.get('admin')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
