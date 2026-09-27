"""Repository PostgreSQL — catalogue articles (prix EUR + label + cost pts)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from db.connection import get_cursor


def _row(row: Any) -> Dict[str, Any]:
    data = dict(row)
    price = data.get("price")
    if isinstance(price, Decimal):
        data["price"] = float(price)
    elif price is not None:
        data["price"] = float(price)
    cost = data.get("cost")
    if cost is not None:
        try:
            data["cost"] = int(cost)
        except (TypeError, ValueError):
            data["cost"] = None
    return data


def get_by_kfc_ids(kfc_item_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Map kfc_item_id -> article pour les ids demandes."""
    ids = sorted({str(i) for i in kfc_item_ids if i})
    if not ids:
        return {}
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, kfc_item_id, name, label, price, cost, updated_at
            FROM article
            WHERE kfc_item_id = ANY(%s)
            """,
            (ids,),
        )
        return {str(r["kfc_item_id"]): _row(r) for r in cur.fetchall()}


def get_by_kfc_id(kfc_item_id: str) -> Optional[Dict[str, Any]]:
    found = get_by_kfc_ids([kfc_item_id])
    return found.get(str(kfc_item_id))


def list_labels() -> List[str]:
    """Labels distincts, ordre alpha (pour affichage categories)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT label
            FROM article
            WHERE label IS NOT NULL AND BTRIM(label) <> ''
            ORDER BY label ASC
            """
        )
        return [str(r["label"]) for r in cur.fetchall()]
