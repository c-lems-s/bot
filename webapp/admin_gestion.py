"""API admin « Gestion » — tables whitelistees + variables shop.

Aucune SQL libre : ressources et champs editables figes cote serveur.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from flask import jsonify, request

from db.connection import get_cursor
from db.repositories import blacklist as blacklist_repo
from db.repositories import config as config_repo
from db.repositories import paiements as paiements_repo
from db.repositories import users as users_repo
from kfc.config import clear_cache
from webapp.access import require_full_admin
from webapp.auth import require_telegram_user

# Ressources exposees dans le panel (pas de SQL libre).
GESTION_RESOURCES = (
    {
        "id": "config",
        "label": "Variables shop",
        "description": "Reduction, devise, admin, ouverture…",
    },
    {
        "id": "articles",
        "label": "Articles",
        "description": "Catalogue prix / labels / points",
    },
    {
        "id": "blacklist",
        "label": "Blacklist restos",
        "description": "Restaurants indisponibles",
    },
    {
        "id": "moyens",
        "label": "Moyens de paiement",
        "description": "Liens de recharge portefeuille",
    },
    {
        "id": "users",
        "label": "Utilisateurs",
        "description": "Soldes et comptes Telegram",
    },
)

_CONFIG_PUBLIC_KEYS = (
    "reduction",
    "currency",
    "version",
    "admin",
    "actif",
    "prochaine_heure",
    "updated_at",
)


def _require_admin() -> Optional[Tuple[Any, int]]:
    return require_full_admin()


def _config_public(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in _CONFIG_PUBLIC_KEYS:
        v = row.get(k)
        if k == "updated_at" and v is not None and hasattr(v, "isoformat"):
            v = v.isoformat()
        out[k] = v
    return out


def _list_articles(limit: int = 200, q: str = "") -> list:
    limit = max(1, min(int(limit or 200), 500))
    q = (q or "").strip()
    with get_cursor() as cur:
        if q:
            cur.execute(
                """
                SELECT id, kfc_item_id, name, label, price, cost, updated_at
                FROM article
                WHERE kfc_item_id ILIKE %s
                   OR COALESCE(name, '') ILIKE %s
                   OR label ILIKE %s
                ORDER BY label ASC, name ASC NULLS LAST
                LIMIT %s
                """,
                (f"%{q}%", f"%{q}%", f"%{q}%", limit),
            )
        else:
            cur.execute(
                """
                SELECT id, kfc_item_id, name, label, price, cost, updated_at
                FROM article
                ORDER BY label ASC, name ASC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
        rows = []
        for r in cur.fetchall() or []:
            rows.append(
                {
                    "id": int(r["id"]),
                    "kfcItemId": r.get("kfc_item_id"),
                    "name": r.get("name") or "",
                    "label": r.get("label") or "",
                    "price": float(r["price"]) if r.get("price") is not None else None,
                    "cost": int(r["cost"]) if r.get("cost") is not None else None,
                    "updatedAt": r["updated_at"].isoformat()
                    if r.get("updated_at")
                    else None,
                }
            )
        return rows


def _parse_article_raw_line(line: str) -> Dict[str, Any]:
    """Parse ``"kfc_item_id" "name" "label" price cost``."""
    s = (line or "").strip()
    if not s:
        raise ValueError("ligne brute vide")
    tokens: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        if s[i] == '"':
            i += 1
            buf: list[str] = []
            while i < n and s[i] != '"':
                if s[i] == "\\" and i + 1 < n:
                    buf.append(s[i + 1])
                    i += 2
                    continue
                buf.append(s[i])
                i += 1
            if i >= n or s[i] != '"':
                raise ValueError('guillemet fermant manquant')
            i += 1
            tokens.append("".join(buf))
        else:
            start = i
            while i < n and not s[i].isspace():
                i += 1
            tokens.append(s[start:i])
    if len(tokens) != 5:
        raise ValueError(
            'attendu 5 champs : "kfc_item_id" "name" "label" price cost'
        )
    try:
        price = float(tokens[3])
    except ValueError as e:
        raise ValueError("price invalide") from e
    try:
        cost = int(float(tokens[4]))
    except ValueError as e:
        raise ValueError("cost invalide") from e
    return {
        "kfc_item_id": tokens[0],
        "name": tokens[1],
        "label": tokens[2],
        "price": price,
        "cost": cost,
    }


def _upsert_article(data: dict, article_id: Optional[int] = None) -> Dict[str, Any]:
    raw_line = data.get("raw") or data.get("rawLine") or data.get("raw_line")
    if isinstance(raw_line, str) and raw_line.strip():
        data = {**data, **_parse_article_raw_line(raw_line)}

    kfc_item_id = str(data.get("kfcItemId") or data.get("kfc_item_id") or "").strip()
    name = str(data.get("name") or "").strip() or None
    label = str(data.get("label") or "").strip()
    if not label:
        raise ValueError("label requis")
    try:
        price = float(data.get("price"))
    except (TypeError, ValueError) as e:
        raise ValueError("price invalide") from e
    if price < 0:
        raise ValueError("price doit etre >= 0")
    cost_raw = data.get("cost", "__missing__")
    if cost_raw == "__missing__":
        cost = None if article_id is None else "__keep__"
    elif cost_raw is None or cost_raw == "":
        cost = None
    else:
        try:
            cost = int(cost_raw)
        except (TypeError, ValueError) as e:
            raise ValueError("cost invalide") from e
        if cost < 0:
            raise ValueError("cost doit etre >= 0")

    with get_cursor() as cur:
        if article_id is None:
            if not kfc_item_id:
                raise ValueError("kfcItemId requis")
            cur.execute(
                """
                INSERT INTO article (kfc_item_id, name, label, price, cost, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (kfc_item_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    label = EXCLUDED.label,
                    price = EXCLUDED.price,
                    cost = EXCLUDED.cost,
                    updated_at = NOW()
                RETURNING id, kfc_item_id, name, label, price, cost, updated_at
                """,
                (kfc_item_id, name, label, price, cost),
            )
        else:
            if cost == "__keep__":
                cur.execute(
                    """
                    UPDATE article
                    SET name = COALESCE(%s, name),
                        label = %s,
                        price = %s,
                        kfc_item_id = COALESCE(NULLIF(%s, ''), kfc_item_id),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, kfc_item_id, name, label, price, cost, updated_at
                    """,
                    (name, label, price, kfc_item_id, int(article_id)),
                )
            else:
                cur.execute(
                    """
                    UPDATE article
                    SET name = COALESCE(%s, name),
                        label = %s,
                        price = %s,
                        cost = %s,
                        kfc_item_id = COALESCE(NULLIF(%s, ''), kfc_item_id),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, kfc_item_id, name, label, price, cost, updated_at
                    """,
                    (name, label, price, cost, kfc_item_id, int(article_id)),
                )
        r = cur.fetchone()
        if not r:
            raise LookupError("article introuvable")
        return {
            "id": int(r["id"]),
            "kfcItemId": r.get("kfc_item_id"),
            "name": r.get("name") or "",
            "label": r.get("label") or "",
            "price": float(r["price"]) if r.get("price") is not None else None,
            "cost": int(r["cost"]) if r.get("cost") is not None else None,
            "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") else None,
        }


def _list_users(limit: int = 100, q: str = "") -> list:
    limit = max(1, min(int(limit or 100), 300))
    q = (q or "").strip()
    with get_cursor() as cur:
        if q:
            like = f"%{q}%"
            cur.execute(
                """
                SELECT id, telegram_id, username, first_name, last_name,
                       balance, is_active, last_seen_at
                FROM users
                WHERE CAST(telegram_id AS TEXT) ILIKE %s
                   OR COALESCE(username, '') ILIKE %s
                   OR COALESCE(first_name, '') ILIKE %s
                ORDER BY last_seen_at DESC NULLS LAST
                LIMIT %s
                """,
                (like, like, like, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, telegram_id, username, first_name, last_name,
                       balance, is_active, last_seen_at
                FROM users
                ORDER BY last_seen_at DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
        out = []
        for r in cur.fetchall() or []:
            out.append(
                {
                    "id": int(r["id"]),
                    "telegramId": int(r["telegram_id"]),
                    "username": r.get("username"),
                    "firstName": r.get("first_name"),
                    "lastName": r.get("last_name"),
                    "balance": float(r["balance"]) if r.get("balance") is not None else 0.0,
                    "isActive": bool(r.get("is_active", True)),
                    "lastSeenAt": r["last_seen_at"].isoformat()
                    if r.get("last_seen_at")
                    else None,
                }
            )
        return out


def _patch_config(data: dict) -> Dict[str, Any]:
    row = config_repo.get()
    if not row:
        raise RuntimeError("config introuvable")

    reduction = row.get("reduction", 100)
    if "reduction" in data:
        try:
            reduction = float(data["reduction"])
        except (TypeError, ValueError) as e:
            raise ValueError("reduction invalide") from e
        reduction = max(0.0, min(100.0, reduction))

    currency = row.get("currency") or "EUR"
    if "currency" in data:
        currency = str(data.get("currency") or "EUR").strip().upper()[:8] or "EUR"

    version = str(row.get("version") or "1")
    if "version" in data:
        version = str(data.get("version") or "1").strip()[:32] or "1"

    admin = row.get("admin")
    if "admin" in data:
        raw = data.get("admin")
        if raw is None or raw == "":
            admin = None
        else:
            try:
                admin = int(raw)
            except (TypeError, ValueError) as e:
                raise ValueError("admin invalide") from e

    actif = bool(row.get("actif", True))
    if "actif" in data:
        actif = bool(data.get("actif"))

    ph = row.get("prochaine_heure")
    if "prochaineHeure" in data or "prochaine_heure" in data:
        raw = data.get("prochaineHeure", data.get("prochaine_heure"))
        ph = str(raw).strip() if raw not in (None, "") else None

    if actif:
        ph = None

    updated = config_repo.upsert(
        account_id=row.get("account_id") or "",
        authorization=row.get("authorization") or row.get("auth_token") or "",
        cookies=row.get("cookies") or {},
        recaptcha_token=row.get("recaptcha_token") or "",
        enable_analytics=bool(row.get("enable_analytics", False)),
        balance=float(row.get("balance") or 0),
        currency=currency,
        reduction=reduction,
        version=version,
        admin=admin,
        actif=actif,
        prochaine_heure=ph,
    )
    clear_cache()
    return _config_public(updated)


def register(app) -> None:
    """Attache les routes /api/admin/gestion/* sur l'app Flask."""

    @app.route("/api/admin/gestion/meta")
    @require_telegram_user
    def api_gestion_meta():
        denied = _require_admin()
        if denied:
            return denied
        return jsonify({"resources": list(GESTION_RESOURCES)})

    @app.route("/api/admin/gestion/config", methods=["GET", "PATCH"])
    @require_telegram_user
    def api_gestion_config():
        denied = _require_admin()
        if denied:
            return denied
        if request.method == "GET":
            row = config_repo.get()
            if not row:
                return jsonify({"error": "config introuvable"}), 404
            return jsonify({"config": _config_public(row)})
        try:
            cfg = _patch_config(request.json or {})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({"config": cfg})

    @app.route("/api/admin/gestion/articles", methods=["GET", "POST"])
    @require_telegram_user
    def api_gestion_articles():
        denied = _require_admin()
        if denied:
            return denied
        if request.method == "GET":
            q = request.args.get("q", "")
            limit = request.args.get("limit", 200)
            try:
                limit = int(limit)
            except (TypeError, ValueError):
                limit = 200
            return jsonify({"articles": _list_articles(limit=limit, q=q)})
        try:
            art = _upsert_article(request.json or {})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"article": art}), 201

    @app.route("/api/admin/gestion/articles/<int:article_id>", methods=["PATCH", "DELETE"])
    @require_telegram_user
    def api_gestion_article_one(article_id: int):
        denied = _require_admin()
        if denied:
            return denied
        if request.method == "DELETE":
            with get_cursor() as cur:
                cur.execute("DELETE FROM article WHERE id = %s RETURNING id", (int(article_id),))
                if not cur.fetchone():
                    return jsonify({"error": "article introuvable"}), 404
            return jsonify({"ok": True})
        try:
            art = _upsert_article(request.json or {}, article_id=article_id)
        except LookupError:
            return jsonify({"error": "article introuvable"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"article": art})

    @app.route("/api/admin/gestion/blacklist", methods=["GET", "POST"])
    @require_telegram_user
    def api_gestion_blacklist():
        denied = _require_admin()
        if denied:
            return denied
        if request.method == "GET":
            with get_cursor() as cur:
                cur.execute(
                    """
                    SELECT store_id, name, city, matched_items, reason, blacklisted_at
                    FROM store_blacklist
                    ORDER BY blacklisted_at DESC NULLS LAST
                    LIMIT 500
                    """
                )
                rows = [
                    {
                        "storeId": str(r["store_id"]),
                        "name": r.get("name") or "",
                        "city": r.get("city") or "",
                        "matchedItems": r.get("matched_items"),
                        "reason": r.get("reason") or "",
                        "blacklistedAt": r["blacklisted_at"].isoformat()
                        if r.get("blacklisted_at")
                        else None,
                    }
                    for r in cur.fetchall() or []
                ]
            return jsonify({"stores": rows})

        data = request.json or {}
        store_id = str(data.get("storeId") or data.get("store_id") or "").strip()
        if not store_id:
            return jsonify({"error": "storeId requis"}), 400
        blacklist_repo.add_store(
            store_id,
            name=str(data.get("name") or ""),
            city=str(data.get("city") or ""),
            reason=str(data.get("reason") or "manual"),
        )
        return jsonify({"ok": True, "storeId": store_id}), 201

    @app.route("/api/admin/gestion/blacklist/<path:store_id>", methods=["DELETE"])
    @require_telegram_user
    def api_gestion_blacklist_del(store_id: str):
        denied = _require_admin()
        if denied:
            return denied
        ok = blacklist_repo.remove_store(str(store_id))
        if not ok:
            return jsonify({"error": "introuvable"}), 404
        return jsonify({"ok": True})

    @app.route("/api/admin/gestion/moyens", methods=["GET", "POST"])
    @require_telegram_user
    def api_gestion_moyens():
        denied = _require_admin()
        if denied:
            return denied
        if request.method == "GET":
            return jsonify({"moyens": paiements_repo.list_moyens()})
        data = request.json or {}
        nom = str(data.get("nom") or "").strip()
        lien = str(data.get("lien") or "").strip()
        if not nom:
            return jsonify({"error": "nom requis"}), 400
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO moyen_paiement (nom, lien)
                VALUES (%s, %s)
                RETURNING id, nom, lien
                """,
                (nom, lien),
            )
            r = cur.fetchone()
        return jsonify(
            {"moyen": {"id": int(r["id"]), "nom": r["nom"], "lien": r.get("lien") or ""}}
        ), 201

    @app.route("/api/admin/gestion/moyens/<int:moyen_id>", methods=["PATCH", "DELETE"])
    @require_telegram_user
    def api_gestion_moyen_one(moyen_id: int):
        denied = _require_admin()
        if denied:
            return denied
        if request.method == "DELETE":
            with get_cursor() as cur:
                cur.execute(
                    "DELETE FROM moyen_paiement WHERE id = %s RETURNING id",
                    (int(moyen_id),),
                )
                if not cur.fetchone():
                    return jsonify({"error": "introuvable"}), 404
            return jsonify({"ok": True})
        data = request.json or {}
        nom = str(data.get("nom") or "").strip()
        lien = data.get("lien")
        with get_cursor() as cur:
            if lien is None:
                cur.execute(
                    """
                    UPDATE moyen_paiement SET nom = COALESCE(NULLIF(%s, ''), nom)
                    WHERE id = %s
                    RETURNING id, nom, lien
                    """,
                    (nom, int(moyen_id)),
                )
            else:
                cur.execute(
                    """
                    UPDATE moyen_paiement
                    SET nom = COALESCE(NULLIF(%s, ''), nom),
                        lien = %s
                    WHERE id = %s
                    RETURNING id, nom, lien
                    """,
                    (nom, str(lien), int(moyen_id)),
                )
            r = cur.fetchone()
            if not r:
                return jsonify({"error": "introuvable"}), 404
        return jsonify(
            {"moyen": {"id": int(r["id"]), "nom": r["nom"], "lien": r.get("lien") or ""}}
        )

    @app.route("/api/admin/gestion/users", methods=["GET"])
    @require_telegram_user
    def api_gestion_users():
        denied = _require_admin()
        if denied:
            return denied
        q = request.args.get("q", "")
        limit = request.args.get("limit", 100)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 100
        return jsonify({"users": _list_users(limit=limit, q=q)})

    @app.route("/api/admin/gestion/users/<int:user_id>", methods=["PATCH"])
    @require_telegram_user
    def api_gestion_user_patch(user_id: int):
        denied = _require_admin()
        if denied:
            return denied
        data = request.json or {}
        u = users_repo.get_by_id(user_id)
        if not u:
            return jsonify({"error": "user introuvable"}), 404

        if "balance" in data:
            try:
                bal = float(data["balance"])
            except (TypeError, ValueError):
                return jsonify({"error": "balance invalide"}), 400
            if bal < 0 or bal > 1_000_000:
                return jsonify({"error": "balance hors limites"}), 400
            with get_cursor() as cur:
                cur.execute(
                    "UPDATE users SET balance = %s WHERE id = %s RETURNING balance",
                    (bal, int(user_id)),
                )
                cur.fetchone()

        if "isActive" in data or "is_active" in data:
            active = bool(data.get("isActive", data.get("is_active")))
            with get_cursor() as cur:
                cur.execute(
                    "UPDATE users SET is_active = %s WHERE id = %s",
                    (active, int(user_id)),
                )

        u2 = users_repo.get_by_id(user_id)
        return jsonify(
            {
                "user": {
                    "id": u2["id"],
                    "telegramId": u2["telegram_id"],
                    "username": u2.get("username"),
                    "firstName": u2.get("first_name"),
                    "balance": float(u2.get("balance") or 0),
                    "isActive": bool(u2.get("is_active", True)),
                }
            }
        )
