"""Repository PostgreSQL — historique des commandes."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from db.connection import get_cursor


def create_order(
    *,
    order_uuid: str,
    order_number: str,
    confirmation_url: str = "",
    store_id: Optional[str] = None,
    store_name: Optional[str] = None,
    store_city: Optional[str] = None,
    status: str = "SUBMITTED",
    total_points: int = 0,
    account_id: Optional[str] = None,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    items: Optional[List[Dict[str, Any]]] = None,
) -> Optional[int]:
    """
    Enregistre une commande + ses lignes.
    Retourne l'id orders, ou None si order_uuid déjà présent.
    """
    items = items or []
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO orders (
                order_uuid, order_number, confirmation_url,
                store_id, store_name, store_city,
                status, total_points, account_id,
                user_id, session_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (order_uuid) DO NOTHING
            RETURNING id
            """,
            (
                str(order_uuid),
                str(order_number),
                confirmation_url or None,
                store_id,
                store_name,
                store_city,
                status,
                max(0, int(total_points or 0)),
                account_id,
                int(user_id) if user_id is not None else None,
                int(session_id) if session_id is not None else None,
            ),
        )
        row = cur.fetchone()
        if not row:
            return None
        order_id = int(row["id"])

        for it in items:
            cost = max(0, int(it.get("cost") or 0))
            qty = max(1, int(it.get("quantity") or 1))
            modgrps = it.get("modgrps")
            if modgrps is None:
                modgrps = []
            cur.execute(
                """
                INSERT INTO order_items (
                    order_id, loyalty_id, name, cost, quantity, modgrps
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    order_id,
                    str(it.get("loyalty_id") or it.get("itemId") or "") or None,
                    it.get("name") or "",
                    cost,
                    qty,
                    json.dumps(modgrps, ensure_ascii=False),
                ),
            )
        return order_id


def update_status(order_uuid: str, status: str) -> int:
    """Met à jour le statut. Retourne le nombre de lignes modifiées."""
    if not order_uuid or not status:
        return 0
    status = status.upper().strip()
    with get_cursor() as cur:
        if status == "CHECKED_IN":
            cur.execute(
                """
                UPDATE orders
                SET status = %s, checked_in_at = NOW()
                WHERE order_uuid = %s
                """,
                (status, str(order_uuid)),
            )
        else:
            cur.execute(
                """
                UPDATE orders
                SET status = %s
                WHERE order_uuid = %s
                """,
                (status, str(order_uuid)),
            )
        return cur.rowcount or 0


def list_orders(limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Liste les commandes recentes (filtre optionnel par user_id)."""
    limit = max(1, min(int(limit or 50), 200))
    with get_cursor() as cur:
        if user_id is not None:
            cur.execute(
                """
                SELECT id, order_uuid, order_number, confirmation_url,
                       store_id, store_name, store_city, status,
                       total_points, account_id, submitted_at, checked_in_at
                FROM orders
                WHERE user_id = %s
                ORDER BY submitted_at DESC
                LIMIT %s
                """,
                (int(user_id), limit),
            )
        else:
            cur.execute(
                """
                SELECT id, order_uuid, order_number, confirmation_url,
                       store_id, store_name, store_city, status,
                       total_points, account_id, submitted_at, checked_in_at
                FROM orders
                ORDER BY submitted_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall() or []
        out = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "orderUUID": r.get("order_uuid"),
                    "orderNumber": r.get("order_number"),
                    "confirmationUrl": r.get("confirmation_url"),
                    "storeId": r.get("store_id"),
                    "storeName": r.get("store_name"),
                    "storeCity": r.get("store_city"),
                    "status": r.get("status"),
                    "totalPoints": r.get("total_points"),
                    "submittedAt": r["submitted_at"].isoformat()
                    if r.get("submitted_at")
                    else None,
                    "checkedInAt": r["checked_in_at"].isoformat()
                    if r.get("checked_in_at")
                    else None,
                }
            )
        return out


def get_order(order_uuid: str) -> Optional[Dict[str, Any]]:
    if not order_uuid:
        return None
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, order_uuid, order_number, confirmation_url,
                   store_id, store_name, store_city, status,
                   total_points, submitted_at, checked_in_at
            FROM orders
            WHERE order_uuid = %s
            """,
            (str(order_uuid),),
        )
        r = cur.fetchone()
        if not r:
            return None
        cur.execute(
            """
            SELECT loyalty_id, name, cost, quantity, modgrps
            FROM order_items
            WHERE order_id = %s
            ORDER BY id ASC
            """,
            (r["id"],),
        )
        items = []
        for it in cur.fetchall() or []:
            items.append(
                {
                    "loyaltyId": it.get("loyalty_id"),
                    "name": it.get("name"),
                    "cost": it.get("cost"),
                    "quantity": it.get("quantity"),
                    "modgrps": it.get("modgrps") or [],
                }
            )
        return {
            "id": r["id"],
            "orderUUID": r.get("order_uuid"),
            "orderNumber": r.get("order_number"),
            "confirmationUrl": r.get("confirmation_url"),
            "storeName": r.get("store_name"),
            "storeCity": r.get("store_city"),
            "status": r.get("status"),
            "totalPoints": r.get("total_points"),
            "submittedAt": r["submitted_at"].isoformat()
            if r.get("submitted_at")
            else None,
            "items": items,
        }
