"""Repository PostgreSQL — sessions de commande par user."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from db.connection import get_cursor


def _row_to_session(row) -> Dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "status": row.get("status") or "IDLE",
        "store_id": row.get("store_id"),
        "store_name": row.get("store_name"),
        "store_city": row.get("store_city"),
        "basket_id": row.get("basket_id"),
        "cart": row.get("cart_json") or [],
        "last_order": row.get("last_order_json"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def get_draft(user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT * FROM sessions
            WHERE user_id = %s AND status = 'DRAFT'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = cur.fetchone()
        return _row_to_session(row) if row else None


def get_open(user_id: int) -> Optional[Dict[str, Any]]:
    """Session DRAFT active (panier local)."""
    return get_draft(user_id)


def get_by_id(session_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT * FROM sessions
            WHERE id = %s AND user_id = %s
            """,
            (int(session_id), int(user_id)),
        )
        row = cur.fetchone()
        return _row_to_session(row) if row else None


def create_draft(
    user_id: int,
    *,
    store_id: str,
    store_name: str = "",
    store_city: str = "",
    basket_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Ferme d'anciens DRAFT du user puis cree une nouvelle session DRAFT."""
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE sessions
            SET status = 'IDLE', updated_at = NOW()
            WHERE user_id = %s AND status = 'DRAFT'
            """,
            (int(user_id),),
        )
        cur.execute(
            """
            INSERT INTO sessions (
                user_id, status, store_id, store_name, store_city,
                basket_id, cart_json, last_order_json, updated_at
            )
            VALUES (%s, 'DRAFT', %s, %s, %s, %s, '[]'::jsonb, NULL, NOW())
            RETURNING *
            """,
            (
                int(user_id),
                store_id,
                store_name or "",
                store_city or "",
                basket_id,
            ),
        )
        return _row_to_session(cur.fetchone())


def save(
    session_id: int,
    user_id: int,
    *,
    status: Optional[str] = None,
    store_id: Optional[str] = None,
    store_name: Optional[str] = None,
    store_city: Optional[str] = None,
    basket_id: Optional[str] = None,
    cart: Optional[List[Dict[str, Any]]] = None,
    last_order: Optional[Dict[str, Any]] = None,
    clear_basket: bool = False,
    clear_last_order: bool = False,
) -> Optional[Dict[str, Any]]:
    sets = ["updated_at = NOW()"]
    params: list = []

    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if store_id is not None:
        sets.append("store_id = %s")
        params.append(store_id)
    if store_name is not None:
        sets.append("store_name = %s")
        params.append(store_name)
    if store_city is not None:
        sets.append("store_city = %s")
        params.append(store_city)
    if clear_basket:
        sets.append("basket_id = NULL")
    elif basket_id is not None:
        sets.append("basket_id = %s")
        params.append(basket_id)
    if cart is not None:
        sets.append("cart_json = %s::jsonb")
        params.append(json.dumps(cart, ensure_ascii=False))
    if clear_last_order:
        sets.append("last_order_json = NULL")
    elif last_order is not None:
        sets.append("last_order_json = %s::jsonb")
        params.append(json.dumps(last_order, ensure_ascii=False))

    params.extend([int(session_id), int(user_id)])
    with get_cursor() as cur:
        cur.execute(
            f"""
            UPDATE sessions
            SET {", ".join(sets)}
            WHERE id = %s AND user_id = %s
            RETURNING *
            """,
            params,
        )
        row = cur.fetchone()
        return _row_to_session(row) if row else None
