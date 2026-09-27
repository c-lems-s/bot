"""API admin « Staff » — gestion des droits + journal (full admin only)."""

from __future__ import annotations

from flask import jsonify, request

from db.repositories import staff as staff_repo
from db.repositories import users as users_repo
from kfc.config import get_admin, is_admin
from webapp.access import require_full_admin
from webapp.auth import require_telegram_user


def register(app) -> None:
    @app.route("/api/admin/staff", methods=["GET", "POST"])
    @require_telegram_user
    def api_staff_list_or_create():
        denied = require_full_admin()
        if denied:
            return denied
        if request.method == "GET":
            return jsonify({"staff": staff_repo.list_staff()})

        data = request.json or {}
        try:
            user_id = int(data.get("userId"))
        except (TypeError, ValueError):
            return jsonify({"error": "userId invalide"}), 400
        can_p = bool(data.get("canPaiements"))
        can_c = bool(data.get("canCommandes"))
        if not can_p and not can_c:
            return jsonify({"error": "Au moins une permission requise"}), 400

        u = users_repo.get_by_id(user_id)
        if not u:
            return jsonify({"error": "user introuvable"}), 404
        if u.get("telegram_id") is not None and is_admin(u.get("telegram_id")):
            return jsonify({"error": "L'admin principal ne peut pas etre staff"}), 400

        try:
            row = staff_repo.upsert(
                user_id, can_paiements=can_p, can_commandes=can_c
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"staff": row}), 201

    @app.route("/api/admin/staff/<int:user_id>", methods=["PATCH", "DELETE"])
    @require_telegram_user
    def api_staff_one(user_id: int):
        denied = require_full_admin()
        if denied:
            return denied
        if request.method == "DELETE":
            ok = staff_repo.remove(user_id)
            if not ok:
                return jsonify({"error": "staff introuvable"}), 404
            return jsonify({"ok": True})

        data = request.json or {}
        existing = staff_repo.get_by_user_id(user_id)
        if not existing:
            return jsonify({"error": "staff introuvable"}), 404
        can_p = (
            bool(data.get("canPaiements"))
            if "canPaiements" in data
            else existing["canPaiements"]
        )
        can_c = (
            bool(data.get("canCommandes"))
            if "canCommandes" in data
            else existing["canCommandes"]
        )
        if not can_p and not can_c:
            return jsonify({"error": "Au moins une permission requise"}), 400
        try:
            row = staff_repo.upsert(
                user_id, can_paiements=can_p, can_commandes=can_c
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"staff": row})

    @app.route("/api/admin/staff/logs")
    @require_telegram_user
    def api_staff_logs():
        denied = require_full_admin()
        if denied:
            return denied
        staff_user_id = request.args.get("userId")
        limit = request.args.get("limit", 100)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 100
        sid = None
        if staff_user_id not in (None, ""):
            try:
                sid = int(staff_user_id)
            except (TypeError, ValueError):
                return jsonify({"error": "userId invalide"}), 400
        return jsonify({"logs": staff_repo.list_logs(staff_user_id=sid, limit=limit)})

    @app.route("/api/admin/staff/users")
    @require_telegram_user
    def api_staff_users_search():
        """Recherche users pour ajout staff (exclut admin principal)."""
        denied = require_full_admin()
        if denied:
            return denied
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", 40)
        try:
            limit = max(1, min(int(limit), 80))
        except (TypeError, ValueError):
            limit = 40
        admin_tid = get_admin()
        from db.connection import get_cursor

        with get_cursor() as cur:
            if q:
                like = f"%{q}%"
                cur.execute(
                    """
                    SELECT u.id, u.telegram_id, u.username, u.first_name, u.last_name,
                           u.balance,
                           EXISTS (SELECT 1 FROM staff s WHERE s.user_id = u.id) AS is_staff
                    FROM users u
                    WHERE u.telegram_id IS NOT NULL
                      AND (%s::bigint IS NULL OR u.telegram_id <> %s)
                      AND (
                        CAST(u.telegram_id AS TEXT) ILIKE %s
                        OR COALESCE(u.username, '') ILIKE %s
                        OR COALESCE(u.first_name, '') ILIKE %s
                      )
                    ORDER BY u.last_seen_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (admin_tid, admin_tid, like, like, like, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT u.id, u.telegram_id, u.username, u.first_name, u.last_name,
                           u.balance,
                           EXISTS (SELECT 1 FROM staff s WHERE s.user_id = u.id) AS is_staff
                    FROM users u
                    WHERE u.telegram_id IS NOT NULL
                      AND (%s::bigint IS NULL OR u.telegram_id <> %s)
                    ORDER BY u.last_seen_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (admin_tid, admin_tid, limit),
                )
            users = [
                {
                    "id": int(r["id"]),
                    "telegramId": int(r["telegram_id"]),
                    "username": r.get("username"),
                    "firstName": r.get("first_name"),
                    "lastName": r.get("last_name"),
                    "balance": float(r["balance"]) if r.get("balance") is not None else 0.0,
                    "isStaff": bool(r.get("is_staff")),
                }
                for r in cur.fetchall() or []
            ]
        return jsonify({"users": users})
