"""
Acces session courante + cache menuItems.

Le menu est persisté en Postgres (sessions.menu_json) pour rester
disponible quel que soit le worker gunicorn qui traite la requete.
Un cache memoire process reste un hot-path.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from db.repositories import sessions as sessions_repo

# Cache menu fidélité par session_id (process local, hydrate depuis DB).
_MENU_CACHE: Dict[int, Dict[str, Any]] = {}


def set_menu_items(session_id: int, items_by_id: Dict[str, Any]) -> None:
    sid = int(session_id)
    payload = items_by_id or {}
    _MENU_CACHE[sid] = payload
    try:
        sessions_repo.save_menu_json(sid, payload)
    except Exception:
        # Ne bloque pas le flux menu si l'écriture cache echoue ;
        # le worker courant garde quand meme le menu en memoire.
        import logging

        logging.getLogger(__name__).exception(
            "save_menu_json echoue (session=%s)", sid
        )


def get_menu_items(session_id: int) -> Dict[str, Any]:
    sid = int(session_id)
    cached = _MENU_CACHE.get(sid)
    if cached is not None:
        return cached
    try:
        from_db = sessions_repo.get_menu_json(sid) or {}
    except Exception:
        from_db = {}
    if from_db:
        _MENU_CACHE[sid] = from_db
    return from_db


def find_menu_item(session_id: int, item_id: str) -> Optional[Dict[str, Any]]:
    return get_menu_items(session_id).get(str(item_id))


def clear_menu_cache(session_id: int) -> None:
    sid = int(session_id)
    _MENU_CACHE.pop(sid, None)
    try:
        sessions_repo.save_menu_json(sid, {})
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "clear menu_json echoue (session=%s)", sid
        )


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
