"""Repository PostgreSQL — utilisateurs Telegram."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from db.connection import get_cursor


def _row_to_user(row: Any) -> Dict[str, Any]:
    data = dict(row)
    bal = data.get("balance")
    if isinstance(bal, Decimal):
        data["balance"] = float(bal)
    elif bal is None:
        data["balance"] = 0.0
    else:
        data["balance"] = float(bal)
    return data


def upsert_from_telegram(
    *,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    language_code: Optional[str] = None,
    initial_balance: float = 0.0,
) -> Dict[str, Any]:
    """Cree ou met a jour un user. Retourne le dict row.

    Le solde est a 0 a la creation. Les connexions suivantes ne l'ecrasent pas.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (
                telegram_id, username, first_name, last_name, language_code,
                balance, last_seen_at
            )
            VALUES (%s, %s, %s, %s, %s, COALESCE(%s, 0), NOW())
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                language_code = COALESCE(EXCLUDED.language_code, users.language_code),
                last_seen_at = NOW(),
                is_active = TRUE
            RETURNING id, telegram_id, username, first_name, last_name,
                      language_code, is_active, balance,
                      first_seen_at, last_seen_at
            """,
            (
                int(telegram_id),
                username,
                first_name,
                last_name,
                language_code,
                float(initial_balance),
            ),
        )
        row = cur.fetchone()
        return _row_to_user(row)


def get_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, telegram_id, username, first_name, last_name,
                   language_code, is_active, balance,
                   first_seen_at, last_seen_at
            FROM users WHERE id = %s
            """,
            (int(user_id),),
        )
        row = cur.fetchone()
        return _row_to_user(row) if row else None


def get_purchase_stats(user_id: int) -> Dict[str, Any]:
    """Nombre d'achats (commandes) + date du dernier achat."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*)::int AS purchase_count,
                MAX(submitted_at) AS last_purchase_at
            FROM orders
            WHERE user_id = %s
            """,
            (int(user_id),),
        )
        row = cur.fetchone() or {}
        last = row.get("last_purchase_at")
        return {
            "purchaseCount": int(row.get("purchase_count") or 0),
            "lastPurchaseAt": last.isoformat() if last else None,
        }


def get_balance(user_id: int) -> float:
    with get_cursor() as cur:
        cur.execute("SELECT balance FROM users WHERE id = %s", (int(user_id),))
        row = cur.fetchone()
        if not row:
            return 0.0
        bal = row["balance"]
        return float(bal) if bal is not None else 0.0


def set_balance(user_id: int, balance: float) -> float:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE users SET balance = %s
            WHERE id = %s
            RETURNING balance
            """,
            (float(balance), int(user_id)),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"user {user_id} introuvable")
        return float(row["balance"])


def credit(user_id: int, amount: float) -> float:
    """Credite le solde (remboursement / correction). Retourne le solde apres."""
    amount = float(amount)
    if amount < 0:
        raise ValueError("montant credit negatif")
    if amount == 0:
        return get_balance(user_id)
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE users
            SET balance = COALESCE(balance, 0) + %s
            WHERE id = %s
            RETURNING balance
            """,
            (amount, int(user_id)),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"user {user_id} introuvable")
        return float(row["balance"])


def debit_if_sufficient(user_id: int, amount: float) -> Tuple[bool, float]:
    """Debite atomiquement si solde >= amount.

    Returns:
        (ok, balance_apres). Si ok=False, balance_apres = solde actuel (ou 0).
    """
    amount = float(amount)
    if amount < 0:
        raise ValueError("montant debit negatif")
    if amount == 0:
        return True, get_balance(user_id)

    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE users
            SET balance = balance - %s
            WHERE id = %s
              AND balance IS NOT NULL
              AND balance >= %s
            RETURNING balance
            """,
            (amount, int(user_id), amount),
        )
        row = cur.fetchone()
        if row:
            return True, float(row["balance"])

        cur.execute("SELECT balance FROM users WHERE id = %s", (int(user_id),))
        cur_row = cur.fetchone()
        if not cur_row or cur_row["balance"] is None:
            return False, 0.0
        return False, float(cur_row["balance"])

