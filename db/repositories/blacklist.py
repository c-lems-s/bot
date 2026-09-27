"""Repository PostgreSQL — blacklist restaurants."""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

from db.connection import get_cursor


def list_ids() -> Set[str]:
    with get_cursor() as cur:
        cur.execute("SELECT store_id FROM store_blacklist")
        return {str(row["store_id"]) for row in cur.fetchall()}


def is_blacklisted(store_id: str) -> bool:
    if not store_id:
        return False
    with get_cursor() as cur:
        cur.execute(
            "SELECT 1 FROM store_blacklist WHERE store_id = %s LIMIT 1",
            (str(store_id),),
        )
        return cur.fetchone() is not None


def get_entry(store_id: str) -> Optional[Dict[str, Any]]:
    if not store_id:
        return None
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT store_id, name, city, matched_items, reason, blacklisted_at
            FROM store_blacklist
            WHERE store_id = %s
            """,
            (str(store_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "name": row.get("name") or "",
            "city": row.get("city") or "",
            "matchedItems": row.get("matched_items"),
            "reason": row.get("reason"),
            "blacklistedAt": row["blacklisted_at"].isoformat()
            if row.get("blacklisted_at")
            else None,
        }


def add_store(
    store_id: str,
    *,
    name: str = "",
    city: str = "",
    matched_items: Optional[int] = None,
    reason: str = "manual",
) -> None:
    if not store_id:
        return
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO store_blacklist (store_id, name, city, matched_items, reason)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (store_id) DO UPDATE SET
                name = COALESCE(NULLIF(EXCLUDED.name, ''), store_blacklist.name),
                city = COALESCE(NULLIF(EXCLUDED.city, ''), store_blacklist.city),
                matched_items = COALESCE(EXCLUDED.matched_items, store_blacklist.matched_items),
                reason = EXCLUDED.reason,
                blacklisted_at = NOW()
            """,
            (str(store_id), name or "", city or "", matched_items, reason),
        )


def remove_store(store_id: str) -> bool:
    if not store_id:
        return False
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM store_blacklist WHERE store_id = %s",
            (str(store_id),),
        )
        return cur.rowcount > 0
