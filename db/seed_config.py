"""Importe un ancien config.json vers la table Postgres `config`.

Usage :
    python -m db.seed_config

Ne lit le fichier qu'une fois pour peupler la DB.
L'app runtime n'utilise plus le fichier.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict


def _legacy_path() -> str:
    env = os.environ.get("KFC_CONFIG")
    if env:
        return env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "config.json")


def seed_config_from_file(path: str | None = None, *, force: bool = False) -> bool:
    """Upsert depuis JSON. Retourne True si un import a eu lieu.

    Par defaut : n'ecrase pas si account_id DB deja renseigne (sauf force=True).
    """
    from db.repositories import config as config_repo
    from kfc.config import clear_cache

    path = path or _legacy_path()
    if not os.path.isfile(path):
        print(f"[seed_config] Pas de fichier {path} — ignore.")
        return False

    with open(path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    existing = config_repo.get()
    current_aid = (existing.get("account_id") if existing else "") or ""
    already = bool(current_aid.strip()) and not current_aid.startswith("VOTRE")
    if already and not force:
        print(
            "[seed_config] Table config deja renseignee "
            f"(account_id={current_aid}). "
            "Relancez avec --force pour ecraser depuis le fichier."
        )
        return False

    cookies = data.get("cookies") or {}
    if not isinstance(cookies, dict):
        cookies = {}

    try:
        balance = float(data.get("balance", 0.98))
    except (TypeError, ValueError):
        balance = 0.98

    try:
        reduction = float(data.get("reduction", 100))
    except (TypeError, ValueError):
        reduction = 100.0

    admin_raw = data.get("admin", "__missing__")
    if admin_raw == "__missing__":
        admin = existing.get("admin") if existing else None
    elif admin_raw is None or admin_raw == "":
        admin = None
    else:
        try:
            admin = int(admin_raw)
        except (TypeError, ValueError):
            admin = existing.get("admin") if existing else None

    config_repo.upsert(
        account_id=str(data.get("account_id") or ""),
        authorization=str(data.get("authorization") or ""),
        cookies={str(k): str(v) for k, v in cookies.items()},
        recaptcha_token=str(data.get("recaptcha_token") or ""),
        enable_analytics=bool(data.get("enable_analytics", False)),
        balance=balance,
        currency=str(data.get("currency") or "EUR"),
        reduction=reduction,
        version=str(data.get("version") or "1"),
        admin=admin,
    )
    clear_cache()
    print(f"[seed_config] Importe depuis {path} -> table config")
    return True


def main() -> None:
    force = "--force" in sys.argv
    seed_config_from_file(force=force)


if __name__ == "__main__":
    main()
