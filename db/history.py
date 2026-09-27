"""Helpers d'écriture historique (ne fait jamais échouer le flux checkout web)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def save_submitted_order(
    *,
    order_uuid: str,
    order_number: str,
    confirmation_url: str = "",
    store_id: Optional[str] = None,
    store_name: Optional[str] = None,
    store_city: Optional[str] = None,
    total_points: int = 0,
    total_eur: Optional[float] = None,
    account_id: Optional[str] = None,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    items: Optional[List[Dict[str, Any]]] = None,
    status: str = "QUEUED",
) -> Optional[int]:
    try:
        from db.repositories import orders as orders_repo

        return orders_repo.create_order(
            order_uuid=order_uuid,
            order_number=order_number,
            confirmation_url=confirmation_url,
            store_id=store_id,
            store_name=store_name,
            store_city=store_city,
            status=status or "QUEUED",
            total_points=total_points,
            total_eur=total_eur,
            account_id=account_id,
            user_id=user_id,
            session_id=session_id,
            items=items or [],
        )
    except Exception as e:
        print(f"[!] Historique DB non enregistre (submit) : {e}")
        return None


def list_recent(limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    try:
        from db.repositories import orders as orders_repo

        return orders_repo.list_orders(limit=limit, user_id=user_id)
    except Exception as e:
        print(f"[!] Lecture historique DB impossible : {e}")
        return []
