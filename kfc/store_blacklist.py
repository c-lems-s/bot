"""Blacklist persistante des restaurants.

API publique stable : is_blacklisted, get_blacklisted_ids, add_store, …
La verification a lieu a la recherche et a la selection de resto.
Les regles d'ajout automatique seront branchees plus tard.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

from db.repositories import blacklist as repo


def get_blacklisted_ids() -> Set[str]:
    return repo.list_ids()


def is_blacklisted(store_id: str) -> bool:
    return repo.is_blacklisted(store_id)


def get_entry(store_id: str) -> Optional[Dict[str, Any]]:
    return repo.get_entry(store_id)


def add_store(
    store_id: str,
    *,
    name: str = "",
    city: str = "",
    matched_items: Optional[int] = None,
    reason: str = "manual",
) -> None:
    """Ajoute un restaurant a la blacklist (idempotent)."""
    repo.add_store(
        store_id,
        name=name,
        city=city,
        matched_items=matched_items,
        reason=reason,
    )


def remove_store(store_id: str) -> bool:
    """Retire un restaurant de la blacklist. Retourne True si present."""
    return repo.remove_store(store_id)
