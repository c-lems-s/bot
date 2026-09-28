"""Checkout local atomique (session DRAFT → CONFIRMED + debit + order)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from db.connection import get_cursor


def finalize_local_checkout(
    *,
    session_id: int,
    user_id: int,
    cart: List[Dict[str, Any]],
    order_uuid: str,
    order_number: str,
    store_id: Optional[str],
    store_name: Optional[str],
    store_city: Optional[str],
    total_points: int,
    total_eur: float,
    items: List[Dict[str, Any]],
    last_order: Dict[str, Any],
) -> Dict[str, Any]:
    """Une seule transaction : lock session DRAFT, debit, order, confirm.

    Returns:
        {"ok": True, "balance": float, "orderId": int}
        ou {"ok": False, "code": "...", "balance": float|None}
    """
    total_eur = float(total_eur)
    total_points = max(0, int(total_points or 0))

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, status
            FROM sessions
            WHERE id = %s AND user_id = %s
            FOR UPDATE
            """,
            (int(session_id), int(user_id)),
        )
        sess = cur.fetchone()
        if not sess:
            return {"ok": False, "code": "SESSION_NOT_FOUND"}
        if (sess.get("status") or "") != "DRAFT":
            return {"ok": False, "code": "SESSION_NOT_DRAFT"}

        cur.execute(
            """
            UPDATE users
            SET balance = balance - %s
            WHERE id = %s
              AND balance IS NOT NULL
              AND balance >= %s
            RETURNING balance
            """,
            (total_eur, int(user_id), total_eur),
        )
        bal_row = cur.fetchone()
        if not bal_row:
            cur.execute("SELECT balance FROM users WHERE id = %s", (int(user_id),))
            cur_bal = cur.fetchone()
            bal = float(cur_bal["balance"]) if cur_bal and cur_bal.get("balance") is not None else 0.0
            return {"ok": False, "code": "INSUFFICIENT", "balance": bal}

        new_balance = float(bal_row["balance"])

        cur.execute(
            """
            INSERT INTO orders (
                order_uuid, order_number, confirmation_url,
                store_id, store_name, store_city,
                status, total_points, total_eur, account_id,
                user_id, session_id, terminer, annulee
            )
            VALUES (%s, %s, NULL, %s, %s, %s, 'QUEUED', %s, %s, NULL, %s, %s, FALSE, FALSE)
            ON CONFLICT (order_uuid) DO NOTHING
            RETURNING id
            """,
            (
                str(order_uuid),
                str(order_number),
                store_id,
                store_name,
                store_city,
                total_points,
                total_eur,
                int(user_id),
                int(session_id),
            ),
        )
        order_row = cur.fetchone()
        if not order_row:
            raise RuntimeError("order_uuid conflict — abort checkout")

        order_id = int(order_row["id"])
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

        cur.execute(
            """
            UPDATE sessions
            SET status = 'CONFIRMED',
                cart_json = '[]'::jsonb,
                last_order_json = %s::jsonb,
                updated_at = NOW()
            WHERE id = %s AND user_id = %s AND status = 'DRAFT'
            RETURNING id
            """,
            (
                json.dumps(last_order, ensure_ascii=False),
                int(session_id),
                int(user_id),
            ),
        )
        confirmed = cur.fetchone()
        if not confirmed:
            raise RuntimeError("session confirm race — abort checkout")

        return {
            "ok": True,
            "balance": new_balance,
            "orderId": order_id,
        }
