"""Repository PostgreSQL — historique des commandes."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from db.connection import get_cursor


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _client_name(row: Any) -> str:
    parts = [
        (row.get("first_name") or "").strip(),
        (row.get("last_name") or "").strip(),
    ]
    name = " ".join(p for p in parts if p)
    if name:
        return name
    uname = (row.get("username") or "").strip()
    if uname:
        return f"@{uname}"
    uid = row.get("user_id")
    return f"User #{uid}" if uid is not None else "Client"


def _items_for(cur, order_id: int) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT loyalty_id, name, cost, quantity, modgrps
        FROM order_items
        WHERE order_id = %s
        ORDER BY id ASC
        """,
        (int(order_id),),
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
    return items


def _order_dict(r: Any, *, items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "id": int(r["id"]),
        "orderUUID": r.get("order_uuid"),
        "orderNumber": r.get("order_number"),
        "confirmationUrl": r.get("confirmation_url"),
        "storeId": r.get("store_id"),
        "storeName": r.get("store_name"),
        "storeCity": r.get("store_city"),
        "status": r.get("status"),
        "totalPoints": r.get("total_points"),
        "totalEur": _f(r.get("total_eur")),
        "terminer": bool(r.get("terminer")),
        "annulee": bool(r.get("annulee")),
        "annulationExplication": r.get("annulation_explication") or "",
        "adminPrenom": r.get("admin_prenom") or "",
        "adminRestaurant": r.get("admin_restaurant") or "",
        "adminHeureMax": r.get("admin_heure_max") or "",
        "adminLienPreuve": r.get("admin_lien_preuve") or "",
        "userId": int(r["user_id"]) if r.get("user_id") is not None else None,
        "submittedAt": r["submitted_at"].isoformat() if r.get("submitted_at") else None,
        "checkedInAt": r["checked_in_at"].isoformat() if r.get("checked_in_at") else None,
        "termineeAt": r["terminee_at"].isoformat() if r.get("terminee_at") else None,
        "items": items if items is not None else [],
    }


_ORDER_COLS = """
    id, order_uuid, order_number, confirmation_url,
    store_id, store_name, store_city, status,
    total_points, total_eur, account_id, user_id,
    terminer, annulee, annulation_explication,
    admin_prenom, admin_restaurant, admin_heure_max, admin_lien_preuve,
    submitted_at, checked_in_at, terminee_at
"""


def create_order(
    *,
    order_uuid: str,
    order_number: str,
    confirmation_url: str = "",
    store_id: Optional[str] = None,
    store_name: Optional[str] = None,
    store_city: Optional[str] = None,
    status: str = "QUEUED",
    total_points: int = 0,
    total_eur: Optional[float] = None,
    account_id: Optional[str] = None,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    items: Optional[List[Dict[str, Any]]] = None,
) -> Optional[int]:
    items = items or []
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO orders (
                order_uuid, order_number, confirmation_url,
                store_id, store_name, store_city,
                status, total_points, total_eur, account_id,
                user_id, session_id, terminer, annulee
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, FALSE)
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
                float(total_eur) if total_eur is not None else None,
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


def list_queued_for_admin(limit: int = 100) -> List[Dict[str, Any]]:
    """File admin : commandes en cours (terminer=false)."""
    limit = max(1, min(int(limit or 100), 200))
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                o.id,
                o.order_number,
                o.order_uuid,
                o.submitted_at,
                u.first_name,
                u.last_name,
                u.username,
                u.id AS user_id
            FROM orders o
            LEFT JOIN users u ON u.id = o.user_id
            WHERE o.terminer = FALSE
            ORDER BY o.submitted_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        out = []
        for r in cur.fetchall() or []:
            name = _client_name(r)
            order_id = r.get("order_number") or str(r.get("id") or "")
            out.append(
                {
                    "id": int(r["id"]),
                    "orderNumber": r.get("order_number"),
                    "orderUUID": r.get("order_uuid"),
                    "clientName": name,
                    "label": f"{name} - {order_id}",
                    "submittedAt": r["submitted_at"].isoformat()
                    if r.get("submitted_at")
                    else None,
                }
            )
        return out


def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT {_ORDER_COLS}
            FROM orders
            WHERE id = %s
            """,
            (int(order_id),),
        )
        r = cur.fetchone()
        if not r:
            return None
        return _order_dict(r, items=_items_for(cur, int(r["id"])))


def complete_order(
    order_id: int,
    *,
    prenom: str = "",
    restaurant: str = "",
    heure_max: str = "",
    lien_preuve: str = "",
) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            f"""
            UPDATE orders
            SET terminer = TRUE,
                annulee = FALSE,
                status = 'DONE',
                admin_prenom = %s,
                admin_restaurant = %s,
                admin_heure_max = %s,
                admin_lien_preuve = %s,
                terminee_at = NOW(),
                annulation_explication = NULL
            WHERE id = %s AND terminer = FALSE
            RETURNING {_ORDER_COLS}
            """,
            (
                (prenom or "").strip() or None,
                (restaurant or "").strip() or None,
                (heure_max or "").strip() or None,
                (lien_preuve or "").strip() or None,
                int(order_id),
            ),
        )
        r = cur.fetchone()
        if not r:
            return None
        return _order_dict(r, items=_items_for(cur, int(r["id"])))


def cancel_order(order_id: int, *, explication: str) -> Optional[Dict[str, Any]]:
    expl = (explication or "").strip()
    if not expl:
        return None
    with get_cursor() as cur:
        cur.execute(
            f"""
            UPDATE orders
            SET terminer = TRUE,
                annulee = TRUE,
                status = 'FAILED',
                annulation_explication = %s,
                terminee_at = NOW()
            WHERE id = %s AND terminer = FALSE
            RETURNING {_ORDER_COLS}
            """,
            (expl, int(order_id)),
        )
        r = cur.fetchone()
        if not r:
            return None
        return _order_dict(r, items=_items_for(cur, int(r["id"])))


def get_ma_commande(user_id: int) -> Optional[Dict[str, Any]]:
    """Commande terminee aujourd'hui (disparait a minuit)."""
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT {_ORDER_COLS}
            FROM orders
            WHERE user_id = %s
              AND terminer = TRUE
              AND terminee_at >= date_trunc('day', NOW())
            ORDER BY terminee_at DESC
            LIMIT 1
            """,
            (int(user_id),),
        )
        r = cur.fetchone()
        if not r:
            return None
        return _order_dict(r, items=_items_for(cur, int(r["id"])))


def list_orders(limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 200))
    with get_cursor() as cur:
        if user_id is not None:
            cur.execute(
                f"""
                SELECT {_ORDER_COLS}
                FROM orders
                WHERE user_id = %s
                ORDER BY submitted_at DESC
                LIMIT %s
                """,
                (int(user_id), limit),
            )
        else:
            cur.execute(
                f"""
                SELECT {_ORDER_COLS}
                FROM orders
                ORDER BY submitted_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        return [_order_dict(r) for r in (cur.fetchall() or [])]
