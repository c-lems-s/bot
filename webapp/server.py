"""
Backend mini-app Telegram — multi-user (panier local + solde EUR).

- Auth : Telegram WebApp initData (webapp/auth.py)
- Isolation app : sessions Postgres par user
- Catalogue : API publique KFC (restos + menu fidélité), checkout local (QUEUED)

Lancement :
    python -m webapp.server
"""

import os
import sys
import threading
import uuid

from flask import Flask, g, jsonify, request, send_file, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from kfc import cities, loyalty  # noqa: E402
from kfc.kfc_api import stores  # noqa: E402
from kfc.config import (  # noqa: E402
    apply_reduction,
    get_currency,
    get_prochaine_heure,
    get_reduction,
    is_shop_actif,
    shop_inactive_message,
)
from webapp.access import (  # noqa: E402
    current_access,
    get_access,
    log_staff_action,
    require_full_admin,
    require_perm,
)
from kfc import store_blacklist  # noqa: E402
from db import history as order_history  # noqa: E402
from db.repositories import articles as articles_repo  # noqa: E402
from db.repositories import paiements as paiements_repo  # noqa: E402
from db.repositories import sessions as sessions_repo  # noqa: E402
from db.repositories import users as users_repo  # noqa: E402
from webapp.auth import require_telegram_user  # noqa: E402
from webapp.boot import prepare_runtime  # noqa: E402
from webapp.env import app_env, bind_host, is_cloud, telegram_webhook_enabled  # noqa: E402
from webapp.paths import ensure_uploads_dirs, paiements_uploads_dir  # noqa: E402
from webapp import session_store  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_PREUVE_BYTES = 8 * 1024 * 1024
MAX_PREUVES_PAR_DEMANDE = 10
MAX_DRAFT_TOPUPS = 3


def _paiements_dir() -> str:
    return str(paiements_uploads_dir())


def _sniff_preuve_type(raw: bytes):
    """Detecte le type reel du fichier (magic bytes). Ignore le MIME client."""
    if raw.startswith(b"%PDF"):
        return ".pdf", "application/pdf"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return ".webp", "image/webp"
    # HEIC/HEIF (ftyp....heic/heif/mif1)
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        brand = raw[8:12]
        if brand in (b"heic", b"heif", b"mif1", b"msf1"):
            return ".heic", "image/heic"
    return None


app = Flask(__name__, static_folder=None)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def _no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


# Routes API accessibles meme si le shop est inactif
_SHOP_OPEN_EXEMPT_PREFIXES = (
    "/api/me",
    "/telegram/",
)


@app.before_request
def _block_if_shop_inactive():
    path = request.path or ""
    if not path.startswith("/api/"):
        return None
    for prefix in _SHOP_OPEN_EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return None
    try:
        if is_shop_actif():
            return None
    except Exception:
        return None
    return jsonify(
        {
            "error": shop_inactive_message(),
            "code": "SHOP_INACTIVE",
            "actif": False,
            "prochaineHeure": get_prochaine_heure(),
        }
    ), 503


POINTS_LIMIT = 2500
SOON_LABEL = "Bientôt disponible"


def _unit_price_from_catalog(art: dict) -> float:
    """Prix client final (catalogue × reduction). Source de verite serveur."""
    original = float(art["price"])
    return apply_reduction(original, get_reduction())


def _reprice_cart(cart: list, session_id: int | None = None) -> list:
    """Recalcule prix/points depuis le catalogue (+ menu session pour les pts)."""
    if not cart:
        return []
    ids = [str(e.get("itemId") or "") for e in cart if e.get("itemId")]
    catalog = articles_repo.get_by_kfc_ids(ids)
    menu = session_store.get_menu_items(session_id) if session_id else {}
    priced = []
    for e in cart:
        item_id = str(e.get("itemId") or "")
        art = catalog.get(item_id)
        if not art or art.get("price") is None or not str(art.get("label") or "").strip():
            raise ValueError(
                f"Article sans prix catalogue : {e.get('name') or item_id}"
            )
        try:
            qty = int(e.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1
        qty = max(1, qty)
        cost = art.get("cost")
        if cost is None and menu.get(item_id):
            cost = menu[item_id].get("cost")
        try:
            cost = int(cost) if cost is not None else None
        except (TypeError, ValueError):
            cost = None
        if cost is None:
            raise ValueError(
                f"Article sans points catalogue : {e.get('name') or item_id}"
            )
        entry = dict(e)
        entry["itemId"] = item_id
        entry["price"] = _unit_price_from_catalog(art)
        entry["cost"] = cost
        entry["quantity"] = qty
        entry.pop("reduction", None)
        entry.pop("originalPrice", None)
        priced.append(entry)
    return priced


def _public_cart_items(cart: list) -> list:
    """Payload panier pour le client : aucun %, aucun prix catalogue brut."""
    return [
        {
            "id": e["uid"],
            "name": e["name"],
            "image": e.get("image", ""),
            "options": e.get("options", []),
            "quantity": e.get("quantity", 1),
            "price": e.get("price"),
        }
        for e in cart
    ]


def _can_add_by_item(session_id: int, points_used: int) -> dict:
    """Flags canAdd par itemId — calcule cote serveur uniquement."""
    points_used = max(0, int(points_used or 0))
    out = {}
    for item_id, it in (session_store.get_menu_items(session_id) or {}).items():
        cost = it.get("cost")
        try:
            cost_i = int(cost) if cost is not None else None
        except (TypeError, ValueError):
            cost_i = None
        if cost_i is None:
            out[str(item_id)] = True
        else:
            out[str(item_id)] = (points_used + cost_i) <= POINTS_LIMIT
    return out


def _cart_public_payload(sess, cart: list) -> dict:
    points = session_store.cart_points(cart)
    return {
        "items": _public_cart_items(cart),
        "points": points,
        "pointsLimit": POINTS_LIMIT,
        "total": session_store.cart_total_eur(cart),
        "currency": get_currency(),
        "canAddByItemId": _can_add_by_item(sess["id"], points) if sess else {},
    }


def _build_store_menu(store_menu, session_id: int, *, points_used: int = 0):
    """Menu resto KFC croise avec table article (prix final uniquement)."""
    menu_items = {}
    raw_items = []

    for items in store_menu.values():
        for it in items:
            item_id = str(it["id"])
            menu_items[item_id] = it
            raw_items.append(it)

    catalog = articles_repo.get_by_kfc_ids(menu_items.keys())
    grouped = {}
    label_order = []
    points_used = max(0, int(points_used or 0))

    for it in raw_items:
        item_id = str(it["id"])
        art = catalog.get(item_id)
        if art and art.get("price") is not None and str(art.get("label") or "").strip():
            label = str(art["label"]).strip()
            price = _unit_price_from_catalog(art)
            cost = art.get("cost")
            if cost is None:
                cost = it.get("cost")
            try:
                cost_i = int(cost) if cost is not None else None
            except (TypeError, ValueError):
                cost_i = None
            available = True
            can_add = cost_i is None or (points_used + cost_i) <= POINTS_LIMIT
        else:
            label = SOON_LABEL
            price = None
            cost_i = None
            try:
                cost_i = int(it.get("cost")) if it.get("cost") is not None else None
            except (TypeError, ValueError):
                cost_i = None
            available = False
            can_add = False

        if label not in grouped:
            grouped[label] = []
            label_order.append(label)

        cached = dict(it)
        if cost_i is not None:
            cached["cost"] = cost_i
        menu_items[item_id] = cached

        grouped[label].append(
            {
                "id": item_id,
                "name": it["name"],
                "cost": cost_i,
                "price": price,
                "available": available,
                "canAdd": bool(available and can_add),
                "image": it.get("image", ""),
                "hasOptions": "modgrps" in it,
            }
        )

    session_store.set_menu_items(session_id, menu_items)

    known_labels = sorted(l for l in label_order if l != SOON_LABEL)
    ordered = known_labels + ([SOON_LABEL] if SOON_LABEL in grouped else [])
    categories = []
    for label in ordered:
        if grouped.get(label):
            categories.append({"name": label, "items": grouped[label]})
    return categories


def _modifier_names(raw_modgrps):
    names = {}
    for g in raw_modgrps or []:
        for mod in g.get("modifiers", []):
            names[str(mod.get("id"))] = mod.get("name", "")
            if mod.get("modgrps"):
                names.update(_modifier_names(mod["modgrps"]))
    return names


def _selected_labels(selected_modgrps, name_map):
    labels = []
    for g in selected_modgrps or []:
        for mod in g.get("modifiers", []):
            nm = name_map.get(str(mod.get("id")))
            if nm and any(c.isalnum() for c in nm):
                labels.append(nm)
            if mod.get("modgrps"):
                labels.extend(_selected_labels(mod["modgrps"], name_map))
    return labels


def _clean_modgrps(modgrps):
    cleaned = []
    for g in modgrps or []:
        real_mods = [
            m for m in g.get("modifiers", [])
            if any(c.isalnum() for c in (m.get("name") or ""))
        ]
        if not real_mods:
            continue
        new_g = dict(g)
        new_mods = []
        for m in real_mods:
            nm = dict(m)
            if m.get("modgrps"):
                nm["modgrps"] = _clean_modgrps(m["modgrps"])
            new_mods.append(nm)
        new_g["modifiers"] = new_mods
        cleaned.append(new_g)
    return cleaned


def _index_selected(selected):
    idx = {}
    for g in selected or []:
        gid = str(g.get("id"))
        mods = {}
        for m in g.get("modifiers", []):
            mods[str(m.get("id"))] = m
        idx[gid] = mods
    return idx


def _complete_modgrps(raw_modgrps, selected_index):
    result = []
    for g in raw_modgrps or []:
        gid = str(g.get("id"))
        gmin = g.get("min", 0) or 0
        gmax = g.get("max", 1) or 1
        sel_mods = selected_index.get(gid, {})

        chosen = [m for m in g.get("modifiers", []) if str(m.get("id")) in sel_mods]
        if not chosen and gmin >= 1:
            chosen = g.get("modifiers", [])[: max(1, gmin)]

        mods_payload = []
        for m in chosen:
            qty = 1 if gmax > 1 else gmax
            entry = {
                "id": m.get("id"),
                "unitPrice": m.get("price", 0) or 0,
                "quantity": qty,
            }
            if m.get("modgrps"):
                sel_mod = sel_mods.get(str(m.get("id")), {})
                nested_index = _index_selected(sel_mod.get("modgrps"))
                sub = _complete_modgrps(m["modgrps"], nested_index)
                if sub:
                    entry["modgrps"] = sub
            mods_payload.append(entry)

        if mods_payload:
            result.append({"id": g.get("id"), "modifiers": mods_payload})
    return result


def _order_payload(sess):
    return {
        "storeId": sess.get("store_id"),
        "storeName": sess.get("store_name"),
        "channel": "Web",
        "device": "Desktop",
        "disposition": "pickup",
        "fulfillment": {"asap": True},
        "items": [dict(e["kfc"]) for e in (sess.get("cart") or []) if e.get("kfc")],
        "loyaltyPointsTotal": session_store.cart_points(sess.get("cart") or []),
    }


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/health")
def api_health():
    """Healthcheck infra (Railway / reverse-proxy) — pas d'auth.

    ``?deep=1`` verifie aussi Postgres + ecriture uploads.
    """
    payload = {"ok": True, "env": app_env()}
    deep = (request.args.get("deep") or "").strip() in ("1", "true", "yes")
    if not deep:
        return jsonify(payload)

    # DB
    db_ok = False
    db_err = None
    try:
        from db.connection import get_cursor

        with get_cursor() as cur:
            cur.execute("SELECT 1 AS n")
            cur.fetchone()
        db_ok = True
    except Exception as e:
        db_err = str(e)

    uploads = ensure_uploads_dirs()
    payload["db"] = {"ok": db_ok, "error": db_err}
    payload["uploads"] = uploads
    payload["ok"] = bool(db_ok and uploads.get("writable"))
    status = 200 if payload["ok"] else 503
    return jsonify(payload), status


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


@app.route("/api/me")
@require_telegram_user
def api_me():
    """Bootstrap session user — aucune donnee table config (reduction, admin id, …)."""
    user = g.user
    try:
        balance = float(user.get("balance", 0) or 0)
    except (TypeError, ValueError):
        balance = 0.0

    from db.repositories import orders as orders_repo

    ma = orders_repo.get_ma_commande(user["id"])
    shop_open = True
    try:
        shop_open = bool(is_shop_actif())
    except Exception:
        shop_open = True

    access = get_access(user.get("telegram_id"))
    return jsonify(
        {
            "balance": balance,
            "currency": get_currency(),
            "hasMaCommande": ma is not None,
            # Droit UI uniquement ; chaque /api/admin/* re-verifie les perms.
            "showAdmin": bool(access),
            "isFullAdmin": bool(access and access.get("fullAdmin")),
            "adminAccess": {
                "commandes": bool(access and access.get("commandes")),
                "paiements": bool(access and access.get("paiements")),
                "gestion": bool(access and access.get("gestion")),
                "notification": bool(access and access.get("notification")),
                "staff": bool(access and access.get("staff")),
            }
            if access
            else None,
            "shopOpen": shop_open,
            "shopMessage": None if shop_open else shop_inactive_message(),
            "prochaineHeure": None if shop_open else get_prochaine_heure(),
            "pointsLimit": POINTS_LIMIT,
        }
    )


@app.route("/api/config")
@require_telegram_user
def api_config_removed():
    """Ancien endpoint — ne plus exposer la config shop."""
    return jsonify(
        {"error": "Endpoint retire. Utilisez /api/me.", "code": "GONE"}
    ), 410


@app.route("/api/wallet")
@require_telegram_user
def api_wallet():
    """Portefeuille : solde EUR, moyens de paiement, historique paiements."""
    user = g.user
    try:
        balance = float(user.get("balance", 0) or 0)
    except (TypeError, ValueError):
        balance = users_repo.get_balance(user["id"])

    return jsonify(
        {
            "balance": balance,
            "currency": get_currency(),
            "moyens": paiements_repo.list_moyens(),
            "paiements": paiements_repo.list_user_paiements(user["id"]),
        }
    )


@app.route("/api/wallet/topup/start", methods=["POST"])
@require_telegram_user
def api_wallet_topup_start():
    """Cree une demande DRAFT pour un moyen de paiement."""
    user = g.user
    data = request.json or {}
    moyen_id = data.get("moyenId")
    try:
        moyen_id = int(moyen_id)
    except (TypeError, ValueError):
        return jsonify({"error": "moyenId invalide"}), 400

    open_n = paiements_repo.count_open_demandes(user["id"])
    if open_n >= MAX_DRAFT_TOPUPS:
        return jsonify(
            {
                "error": (
                    f"Trop de demandes en cours (max {MAX_DRAFT_TOPUPS}). "
                    "Finalisez ou attendez le traitement admin."
                ),
                "code": "TOPUP_LIMIT",
            }
        ), 409

    dem = paiements_repo.create_demande(user["id"], moyen_id)
    if not dem:
        return jsonify({"error": "Moyen de paiement introuvable"}), 404
    return jsonify({"demande": dem})


@app.route("/api/wallet/topup/<int:demande_id>")
@require_telegram_user
def api_wallet_topup_get(demande_id: int):
    user = g.user
    dem = paiements_repo.get_demande(demande_id, user["id"])
    if not dem:
        return jsonify({"error": "Demande introuvable"}), 404
    preuves = paiements_repo.list_preuves(demande_id, user["id"])
    return jsonify({"demande": dem, "preuves": preuves})


@app.route("/api/wallet/topup/<int:demande_id>/preuve", methods=["POST"])
@require_telegram_user
def api_wallet_topup_preuve(demande_id: int):
    """Ajoute une ou plusieurs preuves (multipart: files[] ou file)."""
    user = g.user
    dem = paiements_repo.get_demande(demande_id, user["id"])
    if not dem:
        return jsonify({"error": "Demande introuvable"}), 404
    if dem["status"] != "DRAFT":
        return jsonify({"error": "Demande deja finalisee"}), 409

    files = request.files.getlist("files") or request.files.getlist("file")
    if not files:
        single = request.files.get("file") or request.files.get("preuve")
        files = [single] if single else []
    files = [f for f in files if f and getattr(f, "filename", None)]
    if not files:
        return jsonify({"error": "Aucun fichier envoye"}), 400

    remaining = MAX_PREUVES_PAR_DEMANDE - int(dem.get("preuveCount") or 0)
    if remaining <= 0:
        return jsonify(
            {"error": f"Maximum {MAX_PREUVES_PAR_DEMANDE} preuves par demande."}
        ), 409

    dest_dir = os.path.join(_paiements_dir(), str(demande_id))
    os.makedirs(dest_dir, exist_ok=True)

    added = []
    for f in files[:remaining]:
        raw = f.read(MAX_PREUVE_BYTES + 1)
        if len(raw) > MAX_PREUVE_BYTES:
            return jsonify(
                {"error": f"Fichier trop volumineux (max {MAX_PREUVE_BYTES // (1024 * 1024)} Mo)."}
            ), 400
        if not raw:
            continue

        sniffed = _sniff_preuve_type(raw)
        if not sniffed:
            return jsonify(
                {"error": "Type de fichier non autorise (contenu invalide)."}
            ), 400
        ext, mime = sniffed

        stored = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(dest_dir, stored)
        with open(path, "wb") as out:
            out.write(raw)

        safe_name = os.path.basename(f.filename or stored)
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "._-")[:80] or stored

        row = paiements_repo.add_preuve(
            demande_id,
            user["id"],
            filename=safe_name,
            mime=mime,
            stored_name=stored,
        )
        if row:
            added.append(row)

    dem = paiements_repo.get_demande(demande_id, user["id"])
    preuves = paiements_repo.list_preuves(demande_id, user["id"])
    return jsonify({"ok": True, "added": added, "demande": dem, "preuves": preuves})


def _parse_topup_montant(raw):
    """EUR, 2 decimales, min 1 max 10000. Retourne (ok, value|None)."""
    try:
        montant = float(raw)
    except (TypeError, ValueError):
        return False, None
    if not (1.0 <= montant <= 10000.0):
        return False, None
    cents = round(montant * 100)
    if abs(montant * 100 - cents) > 1e-6:
        return False, None
    return True, cents / 100.0


@app.route("/api/wallet/topup/<int:demande_id>/montant", methods=["POST"])
@require_telegram_user
def api_wallet_topup_montant(demande_id: int):
    """Enregistre le montant apres choix du moyen, avant les preuves."""
    user = g.user
    dem = paiements_repo.get_demande(demande_id, user["id"])
    if not dem:
        return jsonify({"error": "Demande introuvable"}), 404
    if dem["status"] != "DRAFT":
        return jsonify({"error": "Demande deja finalisee"}), 409

    data = request.json or {}
    ok, montant = _parse_topup_montant(data.get("montant"))
    if not ok:
        return jsonify({"error": "montant invalide"}), 400

    updated = paiements_repo.set_montant(demande_id, user["id"], montant)
    if not updated:
        return jsonify({"error": "Impossible d'enregistrer le montant"}), 409
    preuves = paiements_repo.list_preuves(demande_id, user["id"])
    return jsonify({"demande": updated, "preuves": preuves})


@app.route("/api/wallet/topup/<int:demande_id>/finalize", methods=["POST"])
@require_telegram_user
def api_wallet_topup_finalize(demande_id: int):
    user = g.user
    dem = paiements_repo.get_demande(demande_id, user["id"])
    if not dem:
        return jsonify({"error": "Demande introuvable"}), 404
    if dem["status"] == "PENDING":
        return jsonify({"demande": dem, "already": True})
    if dem["status"] != "DRAFT":
        return jsonify({"error": f"Statut invalide : {dem['status']}"}), 409
    if int(dem.get("preuveCount") or 0) < 1:
        return jsonify({"error": "Ajoutez au moins une preuve avant de finaliser."}), 409

    data = request.json or {}
    # Prefer le montant deja enregistre, sinon celui du body
    raw = data.get("montant", dem.get("montant"))
    ok, montant = _parse_topup_montant(raw)
    if not ok:
        return jsonify({"error": "montant invalide"}), 400

    updated = paiements_repo.finalize_demande(
        demande_id, user["id"], montant=montant
    )
    if not updated or updated.get("status") != "PENDING":
        return jsonify({"error": "Finalisation impossible"}), 409

    try:
        from webapp.bot_notify import notify_admin_new_payment, notify_user

        notify_admin_new_payment()
        notify_user(
            user.get("telegram_id"),
            "Votre demande de paiement a ete envoyee. Elle sera traitee sous peu.",
        )
    except Exception:
        app.logger.exception("Notif paiement finalize %s", demande_id)

    return jsonify({"demande": updated})


@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    """Webhook Bot API — secret obligatoire (anti-forgery bot updates)."""
    secret = (os.environ.get("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    if not secret:
        return jsonify({"error": "webhook disabled (TELEGRAM_WEBHOOK_SECRET manquant)"}), 503
    got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not got or got != secret:
        return jsonify({"error": "forbidden"}), 403
    update = request.get_json(silent=True) or {}
    try:
        from webapp.bot_poll import process_update

        process_update(update)
    except Exception:
        app.logger.exception("Erreur webhook Telegram")
    return jsonify({"ok": True})


@app.route("/api/search", methods=["POST"])
@require_telegram_user
def api_search():
    query = (request.json or {}).get("query", "").strip()
    if not query:
        return jsonify({"stores": []})
    if len(query) > 80:
        return jsonify({"error": "Recherche trop longue (max 80 caracteres)."}), 400

    allStores = stores.GetAllStores()
    if allStores is None:
        return jsonify(
            {"error": "Service KFC momentanement indisponible, reessayez."}
        ), 503

    matched = cities.GetMatchingPlace(allStores, query)
    if matched is None:
        return jsonify({"stores": []})

    # Blacklist : badge "indisponible" a la recherche (regles d'ajout plus tard).
    blocked = store_blacklist.get_blacklisted_ids()
    result = []
    for name, city, store_id in matched:
        unavailable = str(store_id) in blocked
        result.append(
            {
                "name": name,
                "city": city,
                "id": store_id,
                "available": not unavailable,
                "unavailableLabel": "KFC indisponible" if unavailable else None,
            }
        )
    return jsonify({"stores": result})


@app.route("/api/select-store", methods=["POST"])
@require_telegram_user
def api_select_store():
    user = g.user
    data = request.json or {}
    storeId = data.get("storeId")
    name = data.get("name", "")
    city = data.get("city", "")
    if not storeId:
        return jsonify({"error": "storeId manquant"}), 400

    if store_blacklist.is_blacklisted(storeId):
        return jsonify(
            {"error": "KFC indisponible", "available": False, "blacklisted": True}
        ), 400

    # Menu PUBLIC du resto (pas de loyaltyinfo / match compte).
    store_menu = loyalty.GetStoreLoyaltyMenu(storeId)
    if store_menu is None:
        return jsonify(
            {
                "error": (
                    "Service d'autoshop indisponible suite a une maintenance, "
                    "veuillez patienter puis reessayer ulterieurement."
                ),
                "code": "AUTOSHOP_UNAVAILABLE",
            }
        ), 503

    sess = sessions_repo.create_draft(
        user["id"],
        store_id=str(storeId),
        store_name=name,
        store_city=city,
    )
    categories = _build_store_menu(store_menu, sess["id"], points_used=0)

    return jsonify(
        {
            "store": {"name": name, "city": city, "id": storeId},
            "categories": categories,
            "available": True,
            "sessionId": sess["id"],
            "currency": get_currency(),
            "points": 0,
            "pointsLimit": POINTS_LIMIT,
        }
    )


@app.route("/api/item-options", methods=["POST"])
@require_telegram_user
def api_item_options():
    user = g.user
    sess = session_store.require_draft_session(user["id"])
    if not sess:
        return jsonify({"error": "Aucune session active"}), 400

    itemId = (request.json or {}).get("itemId")
    it = session_store.find_menu_item(sess["id"], itemId)
    if it is None:
        return jsonify({"error": "Article introuvable"}), 404
    art = articles_repo.get_by_kfc_id(str(it["id"]))
    if (
        not art
        or art.get("price") is None
        or not str(art.get("label") or "").strip()
    ):
        return jsonify(
            {"error": "Article bientot disponible — non commandable."}
        ), 403
    return jsonify(
        {
            "name": it["name"],
            "cost": it.get("cost", 0),
            "price": _unit_price_from_catalog(art),
            "modgrps": _clean_modgrps(it.get("modgrps", [])),
        }
    )


@app.route("/api/add-item", methods=["POST"])
@require_telegram_user
def api_add_item():
    user = g.user
    sess = session_store.require_draft_session(user["id"])
    if not sess:
        return jsonify({"error": "Aucune session active — choisissez un restaurant."}), 400

    data = request.json or {}
    # Ignorer price/cost/reduction eventuels envoyes par le client.
    itemId = data.get("itemId")
    modgrps = data.get("modgrps", [])

    it = session_store.find_menu_item(sess["id"], itemId)
    if it is None:
        return jsonify({"error": "Article introuvable"}), 404

    if sess.get("status") not in ("IDLE", "DRAFT"):
        return jsonify({"error": "Commande deja soumise — recommencez."}), 409

    art = articles_repo.get_by_kfc_id(str(it["id"]))
    if (
        not art
        or art.get("price") is None
        or not str(art.get("label") or "").strip()
    ):
        return jsonify(
            {"error": "Article bientot disponible — non commandable."}
        ), 403

    try:
        unit_price = _unit_price_from_catalog(art)
    except (TypeError, ValueError):
        return jsonify({"error": "Prix article invalide en catalogue."}), 500

    cost = art.get("cost")
    if cost is None:
        cost = it.get("cost")
    try:
        cost = int(cost) if cost is not None else None
    except (TypeError, ValueError):
        cost = None

    if cost is None:
        return jsonify({"error": "Article sans points catalogue — non commandable."}), 403

    cart = list(sess.get("cart") or [])
    try:
        cart = _reprice_cart(cart, session_id=sess["id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    points_now = session_store.cart_points(cart)

    if (points_now + cost) > POINTS_LIMIT:
        return jsonify(
            {
                "error": f"Limite de {POINTS_LIMIT} points depassee "
                f"({points_now} + {cost}).",
                "points": points_now,
                "pointsLimit": POINTS_LIMIT,
            }
        ), 409

    name_map = _modifier_names(it.get("modgrps"))
    options = _selected_labels(modgrps, name_map)
    full_modgrps = _complete_modgrps(it.get("modgrps", []), _index_selected(modgrps))

    cart.append(
        {
            "uid": uuid.uuid4().hex,
            "itemId": str(it["id"]),
            "name": it["name"],
            "image": it.get("image", ""),
            "options": options,
            "cost": cost,
            "price": unit_price,
            "quantity": 1,
            "kfc": {
                "id": it["id"],
                "unitPrice": 0,
                "quantity": 1,
                "modgrps": full_modgrps,
                "loyaltyItem": True,
                "loyaltyPoints": cost or 0,
            },
        }
    )
    sessions_repo.save(sess["id"], user["id"], status="DRAFT", cart=cart)
    payload = _cart_public_payload(sess, cart)
    payload["ok"] = True
    return jsonify(payload)


@app.route("/api/basket")
@require_telegram_user
def api_basket():
    user = g.user
    sess = session_store.require_open_session(user["id"])
    cart = (sess or {}).get("cart") or []
    try:
        cart = _reprice_cart(cart, session_id=sess["id"] if sess else None)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    if sess:
        sessions_repo.save(sess["id"], user["id"], cart=cart)
    return jsonify(_cart_public_payload(sess, cart))


@app.route("/api/remove-item", methods=["POST"])
@require_telegram_user
def api_remove_item():
    user = g.user
    sess = session_store.require_draft_session(user["id"])
    if not sess:
        return jsonify({"error": "Aucune session active"}), 400

    uid = (request.json or {}).get("itemUUID")
    if not uid:
        return jsonify({"error": "Requete invalide"}), 400

    if sess.get("status") not in ("IDLE", "DRAFT"):
        return jsonify({"error": "Impossible de modifier le panier apres soumission."}), 409

    cart = list(sess.get("cart") or [])
    entry = next((e for e in cart if e.get("uid") == uid), None)
    if entry is None:
        return jsonify({"error": "Article introuvable dans le panier"}), 404

    cart = [e for e in cart if e.get("uid") != uid]
    try:
        cart = _reprice_cart(cart, session_id=sess["id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    sessions_repo.save(sess["id"], user["id"], cart=cart)
    payload = _cart_public_payload(sess, cart)
    payload["ok"] = True
    return jsonify(payload)


@app.route("/api/checkout", methods=["POST"])
@require_telegram_user
def api_checkout():
    """Valide le panier : transaction atomique (lock DRAFT + debit + order)."""
    user = g.user
    sess = session_store.require_draft_session(user["id"])
    if not sess:
        return jsonify({"error": "Aucune session active"}), 400

    cart = list(sess.get("cart") or [])
    if not cart:
        return jsonify({"error": "Panier vide"}), 400

    try:
        cart = _reprice_cart(cart, session_id=sess["id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    points_total = session_store.cart_points(cart)
    if points_total > POINTS_LIMIT:
        return jsonify(
            {"error": f"Panier a {points_total} points : limite de {POINTS_LIMIT} depassee."}
        ), 409

    total_eur = session_store.cart_total_eur(cart)
    if total_eur <= 0:
        return jsonify({"error": "Total panier invalide."}), 409

    order_uuid = str(uuid.uuid4())
    order_number = f"L-{order_uuid[:8].upper()}"
    sess = {**sess, "cart": cart}
    snapshot = _order_payload(sess)
    items = [
        {
            "loyalty_id": e.get("itemId"),
            "name": e.get("name"),
            "cost": e.get("cost") or 0,
            "quantity": e.get("quantity") or 1,
            "modgrps": (e.get("kfc") or {}).get("modgrps") or [],
        }
        for e in cart
    ]
    last_order = {
        "number": order_number,
        "uuid": order_uuid,
        "points": points_total,
        "total": total_eur,
        "status": "QUEUED",
        "payload": snapshot,
    }

    from db.repositories import checkout as checkout_repo

    try:
        result = checkout_repo.finalize_local_checkout(
            session_id=sess["id"],
            user_id=user["id"],
            cart=cart,
            order_uuid=order_uuid,
            order_number=order_number,
            store_id=sess.get("store_id"),
            store_name=sess.get("store_name"),
            store_city=sess.get("store_city"),
            total_points=points_total,
            total_eur=total_eur,
            items=items,
            last_order=last_order,
        )
    except Exception:
        app.logger.exception("Checkout atomique echoue")
        return jsonify({"error": "Checkout impossible, reessayez."}), 500

    if not result.get("ok"):
        code = result.get("code")
        if code == "INSUFFICIENT":
            bal = result.get("balance")
            return jsonify(
                {
                    "error": (
                        f"Solde insuffisant ({float(bal or 0):.2f} EUR) "
                        f"pour un panier a {total_eur:.2f} EUR."
                    ),
                    "balance": bal,
                    "total": total_eur,
                }
            ), 409
        if code in ("SESSION_NOT_DRAFT", "SESSION_NOT_FOUND"):
            return jsonify({"error": "Checkout deja en cours ou session invalide."}), 409
        return jsonify({"error": "Checkout refuse."}), 409

    session_store.clear_menu_cache(sess["id"])

    try:
        from webapp.bot_notify import notify_admin_new_order, notify_user

        notify_admin_new_order()
        notify_user(
            user.get("telegram_id"),
            (
                f"Commande enregistree (n° {order_number}). "
                "Elle est en cours de traitement."
            ),
        )
    except Exception:
        app.logger.exception("Notif checkout %s", order_number)

    return jsonify(
        {
            "orderNumber": order_number,
            "orderUUID": order_uuid,
            "points": points_total,
            "total": total_eur,
            "balance": result.get("balance"),
            "currency": get_currency(),
            "status": "QUEUED",
            "order": snapshot,
        }
    )


@app.route("/api/history")
@require_telegram_user
def api_history():
    user = g.user
    limit = request.args.get("limit", 50)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 50
    return jsonify(
        {"orders": order_history.list_recent(limit=limit, user_id=user["id"])}
    )


@app.route("/api/admin/paiements")
@require_telegram_user
def api_admin_paiements():
    """File d'attente recharges PENDING — admin uniquement."""
    denied = require_perm("paiements")
    if denied:
        return denied
    return jsonify({"paiements": paiements_repo.list_pending_for_admin(limit=100)})


@app.route("/api/admin/paiements/<int:demande_id>")
@require_telegram_user
def api_admin_paiement_detail(demande_id: int):
    denied = require_perm("paiements")
    if denied:
        return denied
    dem = paiements_repo.get_demande_by_id(demande_id)
    if not dem or dem.get("status") != "PENDING":
        return jsonify({"error": "Demande introuvable"}), 404
    preuves = paiements_repo.list_preuves(demande_id)
    for p in preuves:
        p["url"] = f"/api/admin/paiements/{demande_id}/preuves/{p['id']}"
    u = users_repo.get_by_id(int(dem["userId"])) if dem.get("userId") else None
    client_name = "Client"
    if u:
        parts = [
            (u.get("first_name") or "").strip(),
            (u.get("last_name") or "").strip(),
        ]
        client_name = " ".join(p for p in parts if p) or (
            f"@{u['username']}" if u.get("username") else f"User #{u.get('id')}"
        )
    return jsonify(
        {
            "paiement": {
                **dem,
                "clientName": client_name,
                "currency": get_currency(),
                "preuves": preuves,
            }
        }
    )


@app.route("/api/admin/paiements/<int:demande_id>/user")
@require_telegram_user
def api_admin_paiement_user(demande_id: int):
    denied = require_perm("paiements")
    if denied:
        return denied
    dem = paiements_repo.get_demande_by_id(demande_id)
    if not dem or not dem.get("userId"):
        return jsonify({"error": "Demande / user introuvable"}), 404
    u = users_repo.get_by_id(int(dem["userId"]))
    if not u:
        return jsonify({"error": "User introuvable"}), 404
    stats = users_repo.get_purchase_stats(int(u["id"]))
    return jsonify(
        {
            "user": {
                "id": u.get("id"),
                "telegramId": u.get("telegram_id"),
                "username": u.get("username"),
                "firstName": u.get("first_name"),
                "lastName": u.get("last_name"),
                "languageCode": u.get("language_code"),
                "balance": u.get("balance"),
                "isActive": u.get("is_active"),
                "firstSeenAt": u["first_seen_at"].isoformat()
                if u.get("first_seen_at") and hasattr(u.get("first_seen_at"), "isoformat")
                else u.get("first_seen_at"),
                "lastSeenAt": u["last_seen_at"].isoformat()
                if u.get("last_seen_at") and hasattr(u.get("last_seen_at"), "isoformat")
                else u.get("last_seen_at"),
                "purchaseCount": stats.get("purchaseCount"),
                "lastPurchaseAt": stats.get("lastPurchaseAt"),
            }
        }
    )


@app.route("/api/admin/paiements/<int:demande_id>/preuves/<int:preuve_id>")
@require_telegram_user
def api_admin_paiement_preuve_file(demande_id: int, preuve_id: int):
    """Sert une preuve — admin uniquement (auth header requis)."""
    denied = require_perm("paiements")
    if denied:
        return denied
    dem = paiements_repo.get_demande_by_id(demande_id)
    if not dem:
        return jsonify({"error": "Demande introuvable"}), 404
    preuves = paiements_repo.list_preuves(demande_id)
    cible = next((p for p in preuves if int(p["id"]) == int(preuve_id)), None)
    if not cible:
        return jsonify({"error": "Preuve introuvable"}), 404
    stored = cible.get("storedName") or ""
    if not stored or "/" in stored or "\\" in stored or ".." in stored:
        return jsonify({"error": "Fichier invalide"}), 400
    path = os.path.join(_paiements_dir(), str(int(demande_id)), stored)
    if not os.path.isfile(path):
        return jsonify({"error": "Fichier introuvable"}), 404
    mime = (cible.get("mime") or "").strip() or "application/octet-stream"
    return send_file(path, mimetype=mime, as_attachment=False, download_name=cible.get("filename") or stored)


@app.route("/api/admin/paiements/<int:demande_id>/accept", methods=["POST"])
@require_telegram_user
def api_admin_paiement_accept(demande_id: int):
    denied = require_perm("paiements")
    if denied:
        return denied
    from webapp.paiement_review import decide_paiement

    payload, err, status = decide_paiement(demande_id, accept=True)
    if err:
        return jsonify({"error": err}), status
    log_staff_action("payment_accept", f"demande #{demande_id}")
    return jsonify(payload)


@app.route("/api/admin/paiements/<int:demande_id>/reject", methods=["POST"])
@require_telegram_user
def api_admin_paiement_reject(demande_id: int):
    denied = require_perm("paiements")
    if denied:
        return denied
    from webapp.paiement_review import decide_paiement

    payload, err, status = decide_paiement(demande_id, accept=False)
    if err:
        return jsonify({"error": err}), status
    log_staff_action("payment_reject", f"demande #{demande_id}")
    return jsonify(payload)


@app.route("/api/admin/orders")
@require_telegram_user
def api_admin_orders():
    """File d'attente commandes en cours — admin uniquement."""
    denied = require_perm("commandes")
    if denied:
        return denied
    from db.repositories import orders as orders_repo

    return jsonify({"orders": orders_repo.list_queued_for_admin(limit=100)})


@app.route("/api/admin/orders/<int:order_id>")
@require_telegram_user
def api_admin_order_detail(order_id: int):
    denied = require_perm("commandes")
    if denied:
        return denied
    from db.repositories import orders as orders_repo

    order = orders_repo.get_order_by_id(order_id)
    if not order:
        return jsonify({"error": "Commande introuvable"}), 404
    return jsonify({"order": order})


@app.route("/api/admin/orders/<int:order_id>/user")
@require_telegram_user
def api_admin_order_user(order_id: int):
    denied = require_perm("commandes")
    if denied:
        return denied
    from db.repositories import orders as orders_repo

    order = orders_repo.get_order_by_id(order_id)
    if not order or not order.get("userId"):
        return jsonify({"error": "Commande / user introuvable"}), 404
    u = users_repo.get_by_id(int(order["userId"]))
    if not u:
        return jsonify({"error": "User introuvable"}), 404
    stats = users_repo.get_purchase_stats(int(u["id"]))
    return jsonify(
        {
            "user": {
                "id": u.get("id"),
                "telegramId": u.get("telegram_id"),
                "username": u.get("username"),
                "firstName": u.get("first_name"),
                "lastName": u.get("last_name"),
                "languageCode": u.get("language_code"),
                "balance": u.get("balance"),
                "isActive": u.get("is_active"),
                "firstSeenAt": u["first_seen_at"].isoformat()
                if u.get("first_seen_at") and hasattr(u.get("first_seen_at"), "isoformat")
                else u.get("first_seen_at"),
                "lastSeenAt": u["last_seen_at"].isoformat()
                if u.get("last_seen_at") and hasattr(u.get("last_seen_at"), "isoformat")
                else u.get("last_seen_at"),
                "purchaseCount": stats.get("purchaseCount"),
                "lastPurchaseAt": stats.get("lastPurchaseAt"),
            }
        }
    )


@app.route("/api/admin/pending-count")
@require_telegram_user
def api_admin_pending_count():
    """Nombre de commandes + paiements non traites (badge Admin)."""
    denied = require_perm("panel")
    if denied:
        return denied
    from webapp.bot_notify import pending_counts

    access = current_access() or {}
    data = pending_counts()
    orders = data["orders"] if access.get("commandes") else 0
    paiements = data["paiements"] if access.get("paiements") else 0
    return jsonify({"orders": orders, "paiements": paiements, "count": orders + paiements})


@app.route("/api/admin/orders/<int:order_id>/complete", methods=["POST"])
@require_telegram_user
def api_admin_order_complete(order_id: int):
    denied = require_perm("commandes")
    if denied:
        return denied
    from db.repositories import orders as orders_repo
    from webapp.bot_notify import notify_user

    data = request.json or {}
    order = orders_repo.complete_order(
        order_id,
        prenom=str(data.get("prenom") or ""),
        restaurant=str(data.get("restaurant") or ""),
        heure_max=str(data.get("heureMax") or data.get("heure_max") or ""),
        lien_preuve=str(data.get("lienPreuve") or data.get("lien_preuve") or ""),
    )
    if not order:
        return jsonify({"error": "Commande introuvable ou deja terminee"}), 409

    client = users_repo.get_by_id(int(order["userId"])) if order.get("userId") else None
    if client:
        notify_user(
            client.get("telegram_id"),
            "Votre commande a ete acceptee. Consultez « Ma commande » pour le detail.",
        )
    log_staff_action("order_complete", f"order #{order_id}")
    return jsonify({"order": order})


@app.route("/api/admin/orders/<int:order_id>/cancel", methods=["POST"])
@require_telegram_user
def api_admin_order_cancel(order_id: int):
    denied = require_perm("commandes")
    if denied:
        return denied
    from db.repositories import orders as orders_repo
    from webapp.bot_notify import notify_user

    data = request.json or {}
    expl = str(data.get("explication") or "").strip()
    expl = " ".join(expl.split())
    if not expl:
        return jsonify({"error": "Explication requise"}), 400
    if len(expl) > 500:
        return jsonify({"error": "Explication trop longue (max 500)."}), 400

    before = orders_repo.get_order_by_id(order_id)
    if not before or before.get("terminer"):
        return jsonify({"error": "Commande introuvable ou deja terminee"}), 409

    order = orders_repo.cancel_order(order_id, explication=expl)
    if not order:
        return jsonify({"error": "Annulation impossible"}), 409

    refund = float(order.get("totalEur") or 0)
    new_bal = None
    if order.get("userId") and refund > 0:
        new_bal = users_repo.credit(int(order["userId"]), refund)

    client = users_repo.get_by_id(int(order["userId"])) if order.get("userId") else None
    if client:
        msg = (
            "Votre commande a ete annulee.\n"
            f"Motif : {expl}\n"
        )
        if refund > 0:
            msg += f"Solde rembourse : {refund:.2f} {get_currency()}."
            if new_bal is not None:
                msg += f"\nNouveau solde : {new_bal:.2f} {get_currency()}."
        msg += "\nConsultez « Ma commande » pour le detail."
        notify_user(client.get("telegram_id"), msg)

    log_staff_action("order_cancel", f"order #{order_id}")
    return jsonify({"order": order, "refund": refund, "balance": new_bal})


@app.route("/api/ma-commande")
@require_telegram_user
def api_ma_commande():
    """Commande terminee du jour (visible jusqu'a minuit)."""
    user = g.user
    from db.repositories import orders as orders_repo

    order = orders_repo.get_ma_commande(user["id"])
    return jsonify({"order": order, "hasMaCommande": order is not None})


from webapp import admin_gestion as _admin_gestion  # noqa: E402
from webapp import admin_notifications as _admin_notifications  # noqa: E402
from webapp import admin_staff as _admin_staff  # noqa: E402

_admin_gestion.register(app)
_admin_notifications.register(app)
_admin_staff.register(app)


def _warm_cache():
    try:
        stores.GetAllStores()
    except Exception:
        pass


def main():
    """Lancement local (Flask). Cloud : preferer gunicorn via webapp.wsgi."""
    try:
        prepare_runtime()
    except Exception as e:
        print(f"[-] PostgreSQL / migrations impossible : {e}")
        print("    Verifiez .env puis : python -m db.ensure_db")
        raise SystemExit(1)

    host = bind_host()
    port = int(os.environ.get("PORT", "8080"))
    print(f"[server] APP_ENV={app_env()} listen http://{host}:{port}")
    if is_cloud():
        print(
            "[server] Mode cloud : pour la prod, preferer "
            "`python -m webapp.boot && gunicorn -c gunicorn.conf.py webapp.wsgi:app`"
        )

    threading.Thread(target=_warm_cache, daemon=True).start()
    try:
        from webapp.bot_poll import start_polling_thread

        if telegram_webhook_enabled():
            print("[server] TELEGRAM_WEBHOOK=1 — poll desactive")
        else:
            start_polling_thread()
    except Exception as e:
        print(f"[!] Poll Telegram ignore : {e}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
