"""Notifications Telegram simples (user / admin) + compteurs file admin."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from db.connection import get_cursor
from kfc.config import get_admin
from webapp import telegram as tg

log = logging.getLogger(__name__)


def notify_user(telegram_id: Optional[int], text: str) -> bool:
    if not telegram_id:
        return False
    try:
        return bool(tg.send_message(int(telegram_id), text, parse_mode=None))
    except Exception:
        log.exception("Notif user echouee (%s)", telegram_id)
        return False


def notify_admin(text: str) -> bool:
    """Message court a l'admin — pas de lien, pas de boutons."""
    admin_id = get_admin()
    if not admin_id:
        log.warning("config.admin manquant — notif admin ignoree")
        return False
    try:
        return bool(tg.send_message(int(admin_id), text, parse_mode=None))
    except Exception:
        log.exception("Notif admin echouee")
        return False


def notify_admin_new_order() -> bool:
    return notify_admin("Nouvel achat")


def notify_admin_new_payment() -> bool:
    return notify_admin("Nouveau paiement")


def pending_counts() -> Dict[str, Any]:
    """Commandes non traitees + paiements PENDING."""
    orders = 0
    paiements = 0
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)::int AS n
            FROM orders
            WHERE COALESCE(terminer, FALSE) = FALSE
            """
        )
        row = cur.fetchone() or {}
        orders = int(row.get("n") or 0)
        cur.execute(
            """
            SELECT COUNT(*)::int AS n
            FROM paiement_demande
            WHERE status = 'PENDING'
            """
        )
        row = cur.fetchone() or {}
        paiements = int(row.get("n") or 0)
    total = orders + paiements
    return {"orders": orders, "paiements": paiements, "count": total}
