"""API admin « Notification » — broadcast Telegram (message + photos + ciblage)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from flask import jsonify, request

from db.connection import get_cursor
from webapp import telegram as tg
from webapp.access import require_full_admin
from webapp.auth import require_telegram_user

log = logging.getLogger(__name__)

UPLOADS_NOTIF_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "uploads", "notifications"
)
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTOS = 10
MAX_MESSAGE_LEN = 4000

# 20 criteres de ciblage (whitelist serveur).
CRITERIA: Tuple[Dict[str, Any], ...] = (
    {
        "id": "all",
        "label": "Tous les users",
        "description": "Tous les comptes avec telegram_id",
        "params": [],
    },
    {
        "id": "active",
        "label": "Users actifs",
        "description": "Comptes marques actifs",
        "params": [],
    },
    {
        "id": "inactive",
        "label": "Users inactifs",
        "description": "Comptes desactives",
        "params": [],
    },
    {
        "id": "recent_order",
        "label": "Commande recente",
        "description": "Au moins une commande dans les X derniers jours",
        "params": [{"key": "days", "label": "Jours", "type": "number", "default": 7}],
    },
    {
        "id": "min_orders",
        "label": "X commandes minimum",
        "description": "Nombre de commandes >= X",
        "params": [{"key": "min", "label": "Minimum", "type": "number", "default": 1}],
    },
    {
        "id": "max_orders",
        "label": "X commandes maximum",
        "description": "Nombre de commandes <= X (inclut 0)",
        "params": [{"key": "max", "label": "Maximum", "type": "number", "default": 0}],
    },
    {
        "id": "no_orders",
        "label": "Aucune commande",
        "description": "Jamais commande",
        "params": [],
    },
    {
        "id": "balance_min",
        "label": "Solde minimum",
        "description": "Solde >= X",
        "params": [{"key": "amount", "label": "Montant", "type": "number", "default": 1}],
    },
    {
        "id": "balance_max",
        "label": "Solde maximum",
        "description": "Solde <= X",
        "params": [{"key": "amount", "label": "Montant", "type": "number", "default": 0}],
    },
    {
        "id": "balance_zero",
        "label": "Solde a zero",
        "description": "Solde exactement 0",
        "params": [],
    },
    {
        "id": "balance_positive",
        "label": "Solde positif",
        "description": "Solde > 0",
        "params": [],
    },
    {
        "id": "recent_seen",
        "label": "Vu recemment",
        "description": "last_seen dans les X derniers jours",
        "params": [{"key": "days", "label": "Jours", "type": "number", "default": 7}],
    },
    {
        "id": "not_seen",
        "label": "Absent depuis X jours",
        "description": "Pas vu depuis au moins X jours",
        "params": [{"key": "days", "label": "Jours", "type": "number", "default": 30}],
    },
    {
        "id": "has_username",
        "label": "Avec username",
        "description": "Username Telegram renseigne",
        "params": [],
    },
    {
        "id": "no_username",
        "label": "Sans username",
        "description": "Pas de username Telegram",
        "params": [],
    },
    {
        "id": "pending_payment",
        "label": "Recharge en attente",
        "description": "Au moins une demande PENDING",
        "params": [],
    },
    {
        "id": "accepted_payment",
        "label": "Deja recharge",
        "description": "Au moins une recharge acceptee",
        "params": [],
    },
    {
        "id": "order_queued",
        "label": "Commande en cours",
        "description": "Commande non terminee",
        "params": [],
    },
    {
        "id": "order_today",
        "label": "Commande aujourd'hui",
        "description": "Au moins une commande soumise aujourd'hui",
        "params": [],
    },
    {
        "id": "spent_min",
        "label": "Depense minimum",
        "description": "Somme total_eur des commandes >= X",
        "params": [{"key": "amount", "label": "Montant EUR", "type": "number", "default": 20}],
    },
)

_CRITERIA_BY_ID = {c["id"]: c for c in CRITERIA}


def _require_admin():
    return require_full_admin()


def _user_public(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(row["id"]),
        "telegramId": int(row["telegram_id"]),
        "username": row.get("username"),
        "firstName": row.get("first_name"),
        "lastName": row.get("last_name"),
        "balance": float(row["balance"]) if row.get("balance") is not None else 0.0,
        "isActive": bool(row.get("is_active", True)),
    }


def _days_param(params: dict, key: str = "days", default: int = 7) -> int:
    try:
        v = int(params.get(key, default))
    except (TypeError, ValueError):
        v = default
    return max(1, min(v, 3650))


def _amount_param(params: dict, key: str = "amount", default: float = 0) -> float:
    try:
        v = float(params.get(key, default))
    except (TypeError, ValueError):
        v = float(default)
    return max(0.0, min(v, 1_000_000.0))


def _int_param(params: dict, key: str, default: int = 0) -> int:
    try:
        v = int(params.get(key, default))
    except (TypeError, ValueError):
        v = default
    return max(0, min(v, 1_000_000))


def resolve_targets(
    criterion_id: str, params: Optional[dict] = None, *, limit: int = 5000
) -> List[Dict[str, Any]]:
    """Retourne les users cibles pour un critere whitelist."""
    meta = _CRITERIA_BY_ID.get(criterion_id)
    if not meta:
        raise ValueError("critere inconnu")
    params = params or {}
    limit = max(1, min(int(limit or 5000), 10000))

    base = """
        SELECT u.id, u.telegram_id, u.username, u.first_name, u.last_name,
               u.balance, u.is_active
        FROM users u
        WHERE u.telegram_id IS NOT NULL
    """
    where = ""
    args: list = []

    if criterion_id == "all":
        where = ""
    elif criterion_id == "active":
        where = "AND COALESCE(u.is_active, TRUE) = TRUE"
    elif criterion_id == "inactive":
        where = "AND COALESCE(u.is_active, TRUE) = FALSE"
    elif criterion_id == "recent_order":
        days = _days_param(params, "days", 7)
        where = """
            AND EXISTS (
                SELECT 1 FROM orders o
                WHERE o.user_id = u.id
                  AND o.submitted_at >= NOW() - (%s || ' days')::interval
            )
        """
        args.append(str(days))
    elif criterion_id == "min_orders":
        mn = _int_param(params, "min", 1)
        where = """
            AND (
                SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id
            ) >= %s
        """
        args.append(mn)
    elif criterion_id == "max_orders":
        mx = _int_param(params, "max", 0)
        where = """
            AND (
                SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id
            ) <= %s
        """
        args.append(mx)
    elif criterion_id == "no_orders":
        where = """
            AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)
        """
    elif criterion_id == "balance_min":
        amount = _amount_param(params, "amount", 1)
        where = "AND COALESCE(u.balance, 0) >= %s"
        args.append(amount)
    elif criterion_id == "balance_max":
        amount = _amount_param(params, "amount", 0)
        where = "AND COALESCE(u.balance, 0) <= %s"
        args.append(amount)
    elif criterion_id == "balance_zero":
        where = "AND COALESCE(u.balance, 0) = 0"
    elif criterion_id == "balance_positive":
        where = "AND COALESCE(u.balance, 0) > 0"
    elif criterion_id == "recent_seen":
        days = _days_param(params, "days", 7)
        where = "AND u.last_seen_at >= NOW() - (%s || ' days')::interval"
        args.append(str(days))
    elif criterion_id == "not_seen":
        days = _days_param(params, "days", 30)
        where = """
            AND (
                u.last_seen_at IS NULL
                OR u.last_seen_at < NOW() - (%s || ' days')::interval
            )
        """
        args.append(str(days))
    elif criterion_id == "has_username":
        where = "AND COALESCE(NULLIF(TRIM(u.username), ''), NULL) IS NOT NULL"
    elif criterion_id == "no_username":
        where = "AND COALESCE(NULLIF(TRIM(u.username), ''), NULL) IS NULL"
    elif criterion_id == "pending_payment":
        where = """
            AND EXISTS (
                SELECT 1 FROM paiement_demande d
                WHERE d.user_id = u.id AND d.status = 'PENDING'
            )
        """
    elif criterion_id == "accepted_payment":
        where = """
            AND (
                EXISTS (
                    SELECT 1 FROM user_paiement p WHERE p.user_id = u.id
                )
                OR EXISTS (
                    SELECT 1 FROM paiement_demande d
                    WHERE d.user_id = u.id AND d.status = 'ACCEPTED'
                )
            )
        """
    elif criterion_id == "order_queued":
        where = """
            AND EXISTS (
                SELECT 1 FROM orders o
                WHERE o.user_id = u.id AND COALESCE(o.terminer, FALSE) = FALSE
            )
        """
    elif criterion_id == "order_today":
        where = """
            AND EXISTS (
                SELECT 1 FROM orders o
                WHERE o.user_id = u.id
                  AND o.submitted_at::date = CURRENT_DATE
            )
        """
    elif criterion_id == "spent_min":
        amount = _amount_param(params, "amount", 20)
        where = """
            AND COALESCE((
                SELECT SUM(COALESCE(o.total_eur, 0)) FROM orders o
                WHERE o.user_id = u.id AND COALESCE(o.annulee, FALSE) = FALSE
            ), 0) >= %s
        """
        args.append(amount)
    else:
        raise ValueError("critere inconnu")

    sql = f"{base} {where} ORDER BY u.last_seen_at DESC NULLS LAST LIMIT %s"
    args.append(limit)

    with get_cursor() as cur:
        cur.execute(sql, tuple(args))
        return [_user_public(dict(r)) for r in cur.fetchall() or []]


def search_users(q: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 100))
    q = (q or "").strip()
    with get_cursor() as cur:
        if q:
            like = f"%{q}%"
            cur.execute(
                """
                SELECT id, telegram_id, username, first_name, last_name,
                       balance, is_active
                FROM users
                WHERE telegram_id IS NOT NULL
                  AND (
                    CAST(telegram_id AS TEXT) ILIKE %s
                    OR COALESCE(username, '') ILIKE %s
                    OR COALESCE(first_name, '') ILIKE %s
                    OR COALESCE(last_name, '') ILIKE %s
                  )
                ORDER BY last_seen_at DESC NULLS LAST
                LIMIT %s
                """,
                (like, like, like, like, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, telegram_id, username, first_name, last_name,
                       balance, is_active
                FROM users
                WHERE telegram_id IS NOT NULL
                ORDER BY last_seen_at DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
        return [_user_public(dict(r)) for r in cur.fetchall() or []]


def users_by_ids(ids: List[int]) -> List[Dict[str, Any]]:
    clean = []
    for i in ids or []:
        try:
            clean.append(int(i))
        except (TypeError, ValueError):
            continue
    if not clean:
        return []
    clean = clean[:5000]
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, telegram_id, username, first_name, last_name,
                   balance, is_active
            FROM users
            WHERE telegram_id IS NOT NULL AND id = ANY(%s)
            """,
            (clean,),
        )
        return [_user_public(dict(r)) for r in cur.fetchall() or []]


def _sniff_image(raw: bytes) -> Optional[Tuple[str, str]]:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def _save_photos(files) -> List[str]:
    os.makedirs(UPLOADS_NOTIF_DIR, exist_ok=True)
    batch = os.path.join(UPLOADS_NOTIF_DIR, uuid.uuid4().hex)
    os.makedirs(batch, exist_ok=True)
    paths: List[str] = []
    for f in files[:MAX_PHOTOS]:
        raw = f.read()
        if not raw or len(raw) > MAX_PHOTO_BYTES:
            continue
        sniffed = _sniff_image(raw)
        if not sniffed:
            continue
        ext, _mime = sniffed
        path = os.path.join(batch, f"{len(paths)}{ext}")
        with open(path, "wb") as out:
            out.write(raw)
        paths.append(path)
    return paths


def _cleanup_paths(paths: List[str]) -> None:
    dirs = set()
    for p in paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
            dirs.add(os.path.dirname(p))
        except Exception:
            pass
    for d in dirs:
        try:
            os.rmdir(d)
        except Exception:
            pass


def send_to_user(telegram_id: int, message: str, photo_paths: List[str]) -> bool:
    """Photos d'abord (debut), puis le texte du message."""
    tid = int(telegram_id)
    paths = [p for p in photo_paths if os.path.isfile(p)]
    ok = True
    if paths:
        if len(paths) == 1:
            sent = tg.send_photo(tid, paths[0])
        else:
            sent = tg.send_media_group(tid, paths)
        if not sent:
            ok = False
    if message:
        sent = tg.send_message(tid, message, parse_mode=None)
        if not sent:
            ok = False
    return ok


def _broadcast_worker(message: str, photo_paths: List[str], targets: List[Dict[str, Any]]) -> None:
    sent = 0
    failed = 0
    try:
        for u in targets:
            tid = u.get("telegramId")
            if not tid:
                failed += 1
                continue
            try:
                if send_to_user(int(tid), message, photo_paths):
                    sent += 1
                else:
                    failed += 1
            except Exception:
                log.exception("Envoi notif user %s", tid)
                failed += 1
            time.sleep(0.05)
        log.info("Broadcast termine: sent=%s failed=%s total=%s", sent, failed, len(targets))
    finally:
        _cleanup_paths(photo_paths)


def register(app) -> None:
    @app.route("/api/admin/notifications/meta")
    @require_telegram_user
    def api_notif_meta():
        denied = _require_admin()
        if denied:
            return denied
        return jsonify({"criteria": list(CRITERIA)})

    @app.route("/api/admin/notifications/users")
    @require_telegram_user
    def api_notif_users():
        denied = _require_admin()
        if denied:
            return denied
        q = request.args.get("q", "")
        limit = request.args.get("limit", 50)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 50
        return jsonify({"users": search_users(q, limit=limit)})

    @app.route("/api/admin/notifications/preview", methods=["POST"])
    @require_telegram_user
    def api_notif_preview():
        denied = _require_admin()
        if denied:
            return denied
        data = request.json or {}
        user_ids = data.get("userIds")
        if user_ids is not None:
            users = users_by_ids(user_ids)
            return jsonify({"count": len(users), "users": users[:50], "mode": "manual"})
        criterion = str(data.get("criterion") or "").strip()
        params = data.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        try:
            users = resolve_targets(criterion, params)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(
            {
                "count": len(users),
                "users": users[:50],
                "mode": "criterion",
                "criterion": criterion,
            }
        )

    @app.route("/api/admin/notifications/send", methods=["POST"])
    @require_telegram_user
    def api_notif_send():
        denied = _require_admin()
        if denied:
            return denied

        # JSON ou multipart
        if request.content_type and "multipart/form-data" in request.content_type:
            message = str(request.form.get("message") or "").strip()
            criterion = str(request.form.get("criterion") or "").strip()
            params_raw = request.form.get("params") or "{}"
            ids_raw = request.form.get("userIds") or "null"
            try:
                params = json.loads(params_raw) if params_raw else {}
            except json.JSONDecodeError:
                params = {}
            try:
                user_ids = json.loads(ids_raw) if ids_raw not in (None, "", "null") else None
            except json.JSONDecodeError:
                return jsonify({"error": "userIds invalide"}), 400
            files = request.files.getlist("photos") or request.files.getlist("photos[]")
            photo_paths = _save_photos(files) if files else []
        else:
            data = request.json or {}
            message = str(data.get("message") or "").strip()
            criterion = str(data.get("criterion") or "").strip()
            params = data.get("params") or {}
            user_ids = data.get("userIds")
            photo_paths = []

        if not isinstance(params, dict):
            params = {}
        if not message and not photo_paths:
            return jsonify({"error": "Message ou photo requis"}), 400
        if len(message) > MAX_MESSAGE_LEN:
            return jsonify({"error": f"Message trop long (max {MAX_MESSAGE_LEN})"}), 400

        if user_ids is not None:
            targets = users_by_ids(user_ids)
        else:
            if not criterion:
                return jsonify({"error": "critere ou userIds requis"}), 400
            try:
                targets = resolve_targets(criterion, params)
            except ValueError as e:
                _cleanup_paths(photo_paths)
                return jsonify({"error": str(e)}), 400

        if not targets:
            _cleanup_paths(photo_paths)
            return jsonify({"error": "Aucun destinataire"}), 400

        if not tg.bot_token():
            _cleanup_paths(photo_paths)
            return jsonify({"error": "TELEGRAM_BOT_TOKEN manquant"}), 503

        threading.Thread(
            target=_broadcast_worker,
            args=(message, photo_paths, targets),
            name="admin-notif-broadcast",
            daemon=True,
        ).start()

        return jsonify(
            {
                "ok": True,
                "queued": len(targets),
                "photos": len(photo_paths),
                "message": "Envoi lance en arriere-plan",
            }
        )
