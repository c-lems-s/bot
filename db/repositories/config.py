"""Repository PostgreSQL — config KFC globale (1 ligne id=1)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, Optional

from db.connection import get_cursor


def _row_to_dict(row: Any) -> Dict[str, Any]:
    data = dict(row)
    cookies = data.get("cookies")
    if cookies is None:
        data["cookies"] = {}
    elif isinstance(cookies, str):
        data["cookies"] = json.loads(cookies) if cookies else {}
    elif not isinstance(cookies, dict):
        data["cookies"] = dict(cookies)

    # Compat API : authorization (ancien nom JSON)
    data["authorization"] = data.get("auth_token") or data.get("authorization") or ""

    bal = data.get("balance")
    if isinstance(bal, Decimal):
        data["balance"] = float(bal)
    elif bal is not None:
        data["balance"] = float(bal)
    else:
        data["balance"] = 0.98

    data["account_id"] = data.get("account_id") or ""
    data["recaptcha_token"] = data.get("recaptcha_token") or ""
    data["enable_analytics"] = bool(data.get("enable_analytics", False))
    data["currency"] = data.get("currency") or "EUR"
    return data


def get() -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, account_id, auth_token, cookies, recaptcha_token,
                   enable_analytics, balance, currency, updated_at
            FROM config
            WHERE id = 1
            """
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def upsert(
    *,
    account_id: str = "",
    authorization: str = "",
    cookies: Optional[Dict[str, str]] = None,
    recaptcha_token: str = "",
    enable_analytics: bool = False,
    balance: float = 0.98,
    currency: str = "EUR",
) -> Dict[str, Any]:
    cookies = cookies or {}
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO config (
                id, account_id, auth_token, cookies, recaptcha_token,
                enable_analytics, balance, currency, updated_at
            )
            VALUES (1, %s, %s, %s::jsonb, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                account_id = EXCLUDED.account_id,
                auth_token = EXCLUDED.auth_token,
                cookies = EXCLUDED.cookies,
                recaptcha_token = EXCLUDED.recaptcha_token,
                enable_analytics = EXCLUDED.enable_analytics,
                balance = EXCLUDED.balance,
                currency = EXCLUDED.currency,
                updated_at = NOW()
            RETURNING id, account_id, auth_token, cookies, recaptcha_token,
                      enable_analytics, balance, currency, updated_at
            """,
            (
                account_id or "",
                authorization or "",
                json.dumps(cookies, ensure_ascii=False),
                recaptcha_token or "",
                bool(enable_analytics),
                float(balance),
                currency or "EUR",
            ),
        )
        row = cur.fetchone()
        return _row_to_dict(row)
