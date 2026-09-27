"""Droits admin / staff pour les APIs panel."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from flask import g, jsonify

from db.repositories import staff as staff_repo
from kfc.config import is_admin


def get_access(telegram_id) -> Optional[Dict[str, Any]]:
    """Retourne les droits panel, ou None si aucun acces."""
    if telegram_id is None:
        return None
    if is_admin(telegram_id):
        return {
            "fullAdmin": True,
            "commandes": True,
            "paiements": True,
            "gestion": True,
            "notification": True,
            "staff": True,
            "staffUserId": None,
        }
    try:
        tid = int(telegram_id)
    except (TypeError, ValueError):
        return None
    row = staff_repo.get_by_telegram_id(tid)
    if not row:
        return None
    return {
        "fullAdmin": False,
        "commandes": bool(row.get("canCommandes")),
        "paiements": bool(row.get("canPaiements")),
        "gestion": False,
        "notification": False,
        "staff": False,
        "staffUserId": row.get("userId"),
    }


def current_access() -> Optional[Dict[str, Any]]:
    user = getattr(g, "user", None) or {}
    return get_access(user.get("telegram_id"))


def require_full_admin():
    access = current_access()
    if not access or not access.get("fullAdmin"):
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
    return None


def require_perm(perm: str):
    """perm: commandes | paiements | gestion | notification | staff | panel."""
    access = current_access()
    if not access:
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
    if perm == "panel":
        if access.get("commandes") or access.get("paiements") or access.get("fullAdmin"):
            return None
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
    if access.get("fullAdmin"):
        return None
    if perm in ("gestion", "notification", "staff"):
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
    if perm == "commandes" and access.get("commandes"):
        return None
    if perm == "paiements" and access.get("paiements"):
        return None
    return jsonify({"error": "Permission insuffisante", "code": "FORBIDDEN"}), 403


def log_staff_action(action: str, detail: str = "") -> None:
    """Enregistre l'action si l'acteur courant est un staff (pas full admin)."""
    access = current_access()
    if not access or access.get("fullAdmin"):
        return
    staff_uid = access.get("staffUserId")
    if not staff_uid:
        return
    user = getattr(g, "user", None) or {}
    try:
        staff_repo.log_action(
            int(staff_uid),
            action,
            actor_telegram_id=user.get("telegram_id"),
            detail=detail,
        )
    except Exception:
        pass
