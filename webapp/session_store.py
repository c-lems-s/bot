"""
Acces session courante + cache menuItems en memoire process.

Remplace le STATE global mono-user.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from db.repositories import sessions as sessions_repo

# Cache menu fidélité par session_id (process local).
_MENU_CACHE: Dict[int, Dict[str, Any]] = {}


def set_menu_items(session_id: int, items_by_id: Dict[str, Any]) -> None:
    _MENU_CACHE[int(session_id)] = items_by_id


def get_menu_items(session_id: int) -> Dict[str, Any]:
    return _MENU_CACHE.get(int(session_id)) or {}


def find_menu_item(session_id: int, item_id: str) -> Optional[Dict[str, Any]]:
    return get_menu_items(session_id).get(str(item_id))


def clear_menu_cache(session_id: int) -> None:
    _MENU_CACHE.pop(int(session_id), None)


def cart_points(cart: List[Dict[str, Any]]) -> int:
    return sum(int(i.get("cost") or 0) for i in (cart or []))


def cart_total_eur(cart: List[Dict[str, Any]]) -> float:
    """Total client EUR (somme price * quantity). Ignore les points KFC."""
    total = 0.0
    for i in cart or []:
        try:
            price = float(i.get("price") or 0)
        except (TypeError, ValueError):
            price = 0.0
        try:
            qty = int(i.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1
        total += price * max(1, qty)
    return round(total, 2)


def require_draft_session(user_id: int) -> Optional[Dict[str, Any]]:
    return sessions_repo.get_draft(user_id)


def require_open_session(user_id: int) -> Optional[Dict[str, Any]]:
    return sessions_repo.get_open(user_id)
