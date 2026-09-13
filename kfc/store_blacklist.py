"""Blacklist persistante des restaurants non éligibles (fidélité).

API publique stable : is_blacklisted, add_store, …
Implémentation : PostgreSQL via db.repositories.blacklist.
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
    reason: str = "loyalty_match",
) -> None:
    """Ajoute un restaurant à la blacklist (idempotent)."""
    repo.add_store(
        store_id,
        name=name,
        city=city,
        matched_items=matched_items,
        reason=reason,
    )


def remove_store(store_id: str) -> bool:
    """Retire un restaurant de la blacklist. Retourne True si présent."""
    return repo.remove_store(store_id)
