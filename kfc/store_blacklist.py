"""Blacklist persistante des restaurants.

API publique : is_blacklisted, get_blacklisted_ids.
Implémentation : PostgreSQL via db.repositories.blacklist.
"""

from __future__ import annotations

from typing import Set

from db.repositories import blacklist as repo


def get_blacklisted_ids() -> Set[str]:
    return repo.list_ids()


def is_blacklisted(store_id: str) -> bool:
    return repo.is_blacklisted(store_id)
