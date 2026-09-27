"""Repository PostgreSQL — config KFC globale (1 ligne id=1)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, Optional

from db.connection import get_cursor

_RETURNING = """
    id, account_id, auth_token, cookies, recaptcha_token,
    enable_analytics, balance, currency, reduction, version,
    admin, actif, prochaine_heure, updated_at
"""


def _row_to_dict(row: Any) -> Dict[str, Any]:
    data = dict(row)
    cookies = data.get("cookies")
    if cookies is None:
        data["cookies"] = {}
    elif isinstance(cookies, str):
        data["cookies"] = json.loads(cookies) if cookies else {}
    elif not isinstance(cookies, dict):
        data["cookies"] = dict(cookies)

    data["authorization"] = data.get("auth_token") or data.get("authorization") or ""

    bal = data.get("balance")
    if isinstance(bal, Decimal):
        data["balance"] = float(bal)
    elif bal is not None:
        data["balance"] = float(bal)
    else:
        data["balance"] = 0.98

    red = data.get("reduction")
    if isinstance(red, Decimal):
        data["reduction"] = float(red)
    elif red is not None:
        data["reduction"] = float(red)
    else:
        data["reduction"] = 100.0

    data["account_id"] = data.get("account_id") or ""
    data["recaptcha_token"] = data.get("recaptcha_token") or ""
    data["enable_analytics"] = bool(data.get("enable_analytics", False))
    data["currency"] = data.get("currency") or "EUR"
    data["version"] = str(data.get("version") or "1")

    admin = data.get("admin")
    if admin is None or admin == "":
        data["admin"] = None
    else:
        try:
            data["admin"] = int(admin)
        except (TypeError, ValueError):
            data["admin"] = None

    if "actif" not in data or data.get("actif") is None:
        data["actif"] = True
    else:
        data["actif"] = bool(data.get("actif"))

    ph = data.get("prochaine_heure")
    data["prochaine_heure"] = (
        str(ph).strip() if ph is not None and str(ph).strip() else None
    )

    return data


def get() -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT {_RETURNING}
            FROM config
            WHERE id = 1
            """
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def set_actif(actif: bool) -> Dict[str, Any]:
    """Active/desactive le shop. Activer (=True) vide toujours prochaine_heure."""
    with get_cursor() as cur:
        if bool(actif):
            cur.execute(
                f"""
                UPDATE config
                SET actif = TRUE,
                    prochaine_heure = NULL,
                    updated_at = NOW()
                WHERE id = 1
                RETURNING {_RETURNING}
                """
            )
        else:
            cur.execute(
                f"""
                UPDATE config
                SET actif = FALSE,
                    updated_at = NOW()
                WHERE id = 1
                RETURNING {_RETURNING}
                """
            )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("config id=1 introuvable")
        return _row_to_dict(row)


def set_prochaine_heure(heure: Optional[str]) -> Dict[str, Any]:
    """Definit la prochaine heure (texte). Impossible si shop actif=true."""
    text = (heure or "").strip() or None
    with get_cursor() as cur:
        cur.execute(
            f"""
            UPDATE config
            SET prochaine_heure = %s,
                updated_at = NOW()
            WHERE id = 1
              AND actif = FALSE
            RETURNING {_RETURNING}
            """,
            (text,),
        )
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT actif FROM config WHERE id = 1")
            check = cur.fetchone()
            if not check:
                raise RuntimeError("config id=1 introuvable")
            if check.get("actif"):
                raise PermissionError(
                    "Impossible de definir une heure tant que le shop est actif."
                )
            raise RuntimeError("Mise a jour prochaine_heure impossible")
        return _row_to_dict(row)


def upsert(
    *,
    account_id: str = "",
    authorization: str = "",
    cookies: Optional[Dict[str, str]] = None,
    recaptcha_token: str = "",
    enable_analytics: bool = False,
    balance: float = 0.98,
    currency: str = "EUR",
    reduction: float = 100.0,
    version: str = "1",
    admin: Optional[int] = None,
    actif: bool = True,
    prochaine_heure: Optional[str] = None,
) -> Dict[str, Any]:
    cookies = cookies or {}
    ph = (str(prochaine_heure).strip() if prochaine_heure else None) or None
    if bool(actif):
        ph = None
    with get_cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO config (
                id, account_id, auth_token, cookies, recaptcha_token,
                enable_analytics, balance, currency, reduction, version,
                admin, actif, prochaine_heure, updated_at
            )
            VALUES (1, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                account_id = EXCLUDED.account_id,
                auth_token = EXCLUDED.auth_token,
                cookies = EXCLUDED.cookies,
                recaptcha_token = EXCLUDED.recaptcha_token,
                enable_analytics = EXCLUDED.enable_analytics,
                balance = EXCLUDED.balance,
                currency = EXCLUDED.currency,
                reduction = EXCLUDED.reduction,
                version = EXCLUDED.version,
                admin = EXCLUDED.admin,
                actif = EXCLUDED.actif,
                prochaine_heure = EXCLUDED.prochaine_heure,
                updated_at = NOW()
            RETURNING {_RETURNING}
            """,
            (
                account_id or "",
                authorization or "",
                json.dumps(cookies, ensure_ascii=False),
                recaptcha_token or "",
                bool(enable_analytics),
                float(balance),
                currency or "EUR",
                float(reduction),
                str(version or "1"),
                int(admin) if admin is not None else None,
                bool(actif),
                ph,
            ),
        )
        row = cur.fetchone()
        return _row_to_dict(row)
