"""Import one-shot de store_blacklist.json vers Postgres."""

from __future__ import annotations

import json
import os
from typing import Any

from db.repositories import blacklist as repo


def _json_path() -> str:
    env = os.environ.get("KFC_STORE_BLACKLIST")
    if env:
        return env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "store_blacklist.json")


def import_blacklist_json(path: str | None = None, *, rename_after: bool = True) -> int:
    """
    Importe le fichier JSON legacy s'il existe.
    Retourne le nombre d'entrees importees.
    Renomme le fichier en .imported pour ne pas reimporter.
    """
    path = path or _json_path()
    if not os.path.isfile(path):
        return 0

    with open(path, "r", encoding="utf-8") as f:
        data: Any = json.load(f)

    stores = data.get("stores") if isinstance(data, dict) else None
    if not isinstance(stores, dict) or not stores:
        if rename_after:
            _rename(path)
        return 0

    count = 0
    for store_id, entry in stores.items():
        if not store_id:
            continue
        entry = entry if isinstance(entry, dict) else {}
        repo.add_store(
            str(store_id),
            name=str(entry.get("name") or ""),
            city=str(entry.get("city") or ""),
            matched_items=entry.get("matchedItems"),
            reason=str(entry.get("reason") or "loyalty_match"),
        )
        count += 1

    if rename_after and count >= 0:
        _rename(path)
    return count


def _rename(path: str) -> None:
    dest = path + ".imported"
    try:
        if os.path.exists(dest):
            os.remove(dest)
        os.replace(path, dest)
    except OSError:
        pass
