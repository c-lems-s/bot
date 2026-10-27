"""Repository PostgreSQL — staff + journal d'actions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from db.connection import get_cursor


def _row(r: Any) -> Dict[str, Any]:
    return {
        "userId": int(r["user_id"]),
        "telegramId": int(r["telegram_id"]) if r.get("telegram_id") is not None else None,
        "username": r.get("username"),
        "firstName": r.get("first_name"),
        "lastName": r.get("last_name"),
        "canPaiements": bool(r.get("can_paiements")),
        "canCommandes": bool(r.get("can_commandes")),
        "createdAt": r["created_at"].isoformat() if r.get("created_at") else None,
        "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None,
    }


def list_staff() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT s.user_id, s.can_paiements, s.can_commandes,
                   s.created_at, s.updated_at,
                   u.telegram_id, u.username, u.first_name, u.last_name
            FROM staff s
            JOIN users u ON u.id = s.user_id
            ORDER BY s.updated_at DESC
            """
        )
        return [_row(r) for r in cur.fetchall() or []]


def get_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT s.user_id, s.can_paiements, s.can_commandes,
                   s.created_at, s.updated_at,
                   u.telegram_id, u.username, u.first_name, u.last_name
            FROM staff s
            JOIN users u ON u.id = s.user_id
            WHERE s.user_id = %s
            """,
            (int(user_id),),
        )
        r = cur.fetchone()
        return _row(r) if r else None


def get_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT s.user_id, s.can_paiements, s.can_commandes,
                   s.created_at, s.updated_at,
                   u.telegram_id, u.username, u.first_name, u.last_name
            FROM staff s
            JOIN users u ON u.id = s.user_id
            WHERE u.telegram_id = %s
            """,
            (int(telegram_id),),
        )
        r = cur.fetchone()
        return _row(r) if r else None


def upsert(
    user_id: int, *, can_paiements: bool, can_commandes: bool
) -> Dict[str, Any]:
    if not can_paiements and not can_commandes:
        raise ValueError("Au moins une permission requise")
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO staff (user_id, can_paiements, can_commandes, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                can_paiements = EXCLUDED.can_paiements,
                can_commandes = EXCLUDED.can_commandes,
                updated_at = NOW()
            RETURNING user_id
            """,
            (int(user_id), bool(can_paiements), bool(can_commandes)),
        )
        if not cur.fetchone():
            raise RuntimeError("upsert staff echoue")
    row = get_by_user_id(user_id)
    if not row:
        raise RuntimeError("staff introuvable apres upsert")
    return row


def remove(user_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM staff WHERE user_id = %s RETURNING user_id",
            (int(user_id),),
        )
        return cur.fetchone() is not None


def log_action(
    staff_user_id: int,
    action: str,
    *,
    actor_telegram_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO staff_action_log (
                staff_user_id, actor_telegram_id, action, detail, created_at
            )
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (
                int(staff_user_id),
                int(actor_telegram_id) if actor_telegram_id is not None else None,
                str(action or "")[:80],
                (detail or "")[:2000] or None,
            ),
        )


def list_logs(
    *, staff_user_id: Optional[int] = None, limit: int = 100
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 100), 300))
    with get_cursor() as cur:
        if staff_user_id is not None:
            cur.execute(
                """
                SELECT l.id, l.staff_user_id, l.actor_telegram_id, l.action,
                       l.detail, l.created_at,
                       u.username, u.first_name, u.telegram_id
                FROM staff_action_log l
                LEFT JOIN users u ON u.id = l.staff_user_id
                WHERE l.staff_user_id = %s
                ORDER BY l.created_at DESC
                LIMIT %s
                """,
                (int(staff_user_id), limit),
            )
        else:
            cur.execute(
                """
                SELECT l.id, l.staff_user_id, l.actor_telegram_id, l.action,
                       l.detail, l.created_at,
                       u.username, u.first_name, u.telegram_id
                FROM staff_action_log l
                LEFT JOIN users u ON u.id = l.staff_user_id
                ORDER BY l.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
        out = []
        for r in cur.fetchall() or []:
            out.append(
                {
                    "id": int(r["id"]),
                    "staffUserId": int(r["staff_user_id"]),
                    "actorTelegramId": int(r["actor_telegram_id"])
                    if r.get("actor_telegram_id") is not None
                    else None,
                    "action": r.get("action") or "",
                    "detail": r.get("detail") or "",
                    "createdAt": r["created_at"].isoformat()
                    if r.get("created_at")
                    else None,
                    "username": r.get("username"),
                    "firstName": r.get("first_name"),
                    "telegramId": int(r["telegram_id"])
                    if r.get("telegram_id") is not None
                    else None,
                }
            )
        return out
