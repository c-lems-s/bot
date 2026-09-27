"""
Backend mini-app Telegram — multi-user, un seul compte KFC (table config).

- Auth : Telegram WebApp initData (webapp/auth.py)
- Isolation app : sessions Postgres par user (plus de STATE global)
- Compte KFC : partage volontaire, pas de lock concurrence en V1

Lancement :
    python -m webapp.server
"""

import os
import sys
import threading
import uuid

from flask import Flask, g, jsonify, request, send_from_directory

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
    get_version,
    is_admin,
    is_shop_actif,
    shop_inactive_message,
)
from kfc import store_blacklist  # noqa: E402
from db import history as order_history  # noqa: E402
from db.ensure_db import ensure_database  # noqa: E402
from db.repositories import articles as articles_repo  # noqa: E402
from db.repositories import paiements as paiements_repo  # noqa: E402
from db.repositories import sessions as sessions_repo  # noqa: E402
from db.repositories import users as users_repo  # noqa: E402
from webapp.auth import require_telegram_user  # noqa: E402
from webapp import session_store  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "paiements")
ALLOWED_PREUVE_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/pdf",
}
MAX_PREUVE_BYTES = 8 * 1024 * 1024
MAX_PREUVES_PAR_DEMANDE = 10

app = Flask(__name__, static_folder=None)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def _no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


# Routes API accessibles meme si le shop est inactif
_SHOP_OPEN_EXEMPT_PREFIXES = (
    "/api/config",
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


def _account_configured():
    """Legacy : plus requis pour le flux panier local."""
    return True


def _build_store_menu(store_menu, session_id: int):
    """Menu resto KFC croise avec table article (prix/label/cost)."""
    menu_items = {}
    raw_items = []
    reduction = get_reduction()

    for items in store_menu.values():
        for it in items:
            item_id = str(it["id"])
            menu_items[item_id] = it
            raw_items.append(it)

    catalog = articles_repo.get_by_kfc_ids(menu_items.keys())
    grouped = {}
    label_order = []

    for it in raw_items:
        item_id = str(it["id"])
        art = catalog.get(item_id)
        if art and art.get("price") is not None and str(art.get("label") or "").strip():
            label = str(art["label"]).strip()
            original_price = float(art["price"])
            price = apply_reduction(original_price, reduction)
            cost = art.get("cost")
            if cost is None:
                cost = it.get("cost")
            available = True
        else:
            label = SOON_LABEL
            original_price = None
            price = None
            cost = it.get("cost")
            available = False

        if label not in grouped:
            grouped[label] = []
            label_order.append(label)

        # Enrichit le cache menu avec cost catalogue (plafond pts)
        cached = dict(it)
        if cost is not None:
            cached["cost"] = cost
        menu_items[item_id] = cached

        grouped[label].append(
            {
                "id": item_id,
                "name": it["name"],
                "cost": cost,
                "originalPrice": original_price,
                "price": price,
                "reduction": reduction,
                "available": available,
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
        "basketId": None,
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


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


@app.route("/api/config")
@require_telegram_user
def api_config():
    user = g.user
    # Solde EUR propre a l'utilisateur (DB) — pas le balance seed table config
    try:
        balance = float(user.get("balance", 0) or 0)
    except (TypeError, ValueError):
        balance = 0.0

    from webapp.auth import _dev_auth_enabled
    from db.repositories import orders as orders_repo

    ma = orders_repo.get_ma_commande(user["id"])

    payload = {
        "configured": _account_configured(),
        "balance": balance,
        "currency": get_currency(),
        "reduction": get_reduction(),
        "isAdmin": is_admin(user.get("telegram_id")),
        "hasMaCommande": ma is not None,
        "actif": is_shop_actif(),
        "prochaineHeure": get_prochaine_heure(),
        "inactiveMessage": None if is_shop_actif() else shop_inactive_message(),
        "user": {
            "id": user["id"],
            "telegramId": user["telegram_id"],
            "username": user.get("username"),
            "firstName": user.get("first_name"),
        },
    }
    if _dev_auth_enabled():
        payload["devAuth"] = True
        payload["version"] = get_version()
    return jsonify(payload)


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

    dest_dir = os.path.join(UPLOADS_DIR, str(demande_id))
    os.makedirs(dest_dir, exist_ok=True)

    added = []
    for f in files[:remaining]:
        mime = (f.mimetype or "").lower().strip()
        if mime and mime not in ALLOWED_PREUVE_MIME:
            return jsonify(
                {"error": f"Type de fichier non autorise : {mime or 'inconnu'}"}
            ), 400

        raw = f.read(MAX_PREUVE_BYTES + 1)
        if len(raw) > MAX_PREUVE_BYTES:
            return jsonify(
                {"error": f"Fichier trop volumineux (max {MAX_PREUVE_BYTES // (1024 * 1024)} Mo)."}
            ), 400
        if not raw:
            continue

        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".pdf"):
            if mime == "image/png":
                ext = ".png"
            elif mime in ("image/jpeg", "image/jpg"):
                ext = ".jpg"
            elif mime == "image/webp":
                ext = ".webp"
            elif mime == "application/pdf":
                ext = ".pdf"
            else:
                ext = ".bin"

        stored = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(dest_dir, stored)
        with open(path, "wb") as out:
            out.write(raw)

        row = paiements_repo.add_preuve(
            demande_id,
            user["id"],
            filename=os.path.basename(f.filename or stored),
            mime=mime or None,
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
        from webapp.paiement_review import notify_admin_paiement

        ok_notif = notify_admin_paiement(demande_id)
        if not ok_notif:
            app.logger.warning(
                "Notif admin echouee pour demande %s (admin/token ?)", demande_id
            )
    except Exception:
        app.logger.exception("Erreur notif admin demande %s", demande_id)

    return jsonify({"demande": updated})


@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    """Webhook Bot API (si TELEGRAM_WEBHOOK=1). Sinon utiliser le poll."""
    secret = (os.environ.get("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    if secret:
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if got != secret:
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

    allStores = stores.GetAllStores()
    if allStores is None:
        return jsonify(
            {"error": "Service KFC momentanement indisponible, reessayez."}
        ), 503

    matched = cities.GetMatchingPlace(allStores, query)
    if matched is None:
        return jsonify({"stores": []})

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
        basket_id=None,
    )
    categories = _build_store_menu(store_menu, sess["id"])

    return jsonify(
        {
            "store": {"name": name, "city": city, "id": storeId},
            "categories": categories,
            "connected": False,
            "liveOrdering": False,
            "matchedItems": None,
            "available": True,
            "sessionId": sess["id"],
            "reduction": get_reduction(),
            "currency": get_currency(),
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
    original = float(art["price"])
    reduction = get_reduction()
    return jsonify(
        {
            "name": it["name"],
            "cost": it.get("cost", 0),
            "originalPrice": original,
            "price": apply_reduction(original, reduction),
            "reduction": reduction,
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
        original_price = float(art["price"])
    except (TypeError, ValueError):
        return jsonify({"error": "Prix article invalide en catalogue."}), 500

    reduction = get_reduction()
    unit_price = apply_reduction(original_price, reduction)

    # Points catalogue (table article), pas le compte KFC
    cost = art.get("cost")
    if cost is None:
        cost = it.get("cost")
    try:
        cost = int(cost) if cost is not None else None
    except (TypeError, ValueError):
        cost = None

    cart = list(sess.get("cart") or [])
    points_now = session_store.cart_points(cart)

    if cost is not None and (points_now + cost) > POINTS_LIMIT:
        return jsonify(
            {
                "error": f"Limite de {POINTS_LIMIT} points depassee "
                f"({points_now} + {cost}).",
                "points": points_now,
                "limit": POINTS_LIMIT,
            }
        ), 409

    name_map = _modifier_names(it.get("modgrps"))
    options = _selected_labels(modgrps, name_map)
    full_modgrps = _complete_modgrps(it.get("modgrps", []), _index_selected(modgrps))

    cart.append(
        {
            "uid": uuid.uuid4().hex,
            "kfcItemId": None,
            "itemId": str(it["id"]),
            "name": it["name"],
            "image": it.get("image", ""),
            "options": options,
            "cost": cost,
            "originalPrice": original_price,
            "price": unit_price,
            "reduction": reduction,
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
    return jsonify(
        {
            "ok": True,
            "points": session_store.cart_points(cart),
            "limit": POINTS_LIMIT,
            "total": session_store.cart_total_eur(cart),
            "currency": get_currency(),
            "liveOrdering": False,
        }
    )


@app.route("/api/basket")
@require_telegram_user
def api_basket():
    user = g.user
    sess = session_store.require_open_session(user["id"])
    cart = (sess or {}).get("cart") or []
    items = [
        {
            "id": e["uid"],
            "name": e["name"],
            "image": e.get("image", ""),
            "options": e.get("options", []),
            "quantity": e.get("quantity", 1),
            "originalPrice": e.get("originalPrice"),
            "price": e.get("price"),
            "reduction": e.get("reduction"),
        }
        for e in cart
    ]
    return jsonify(
        {
            "items": items,
            "points": session_store.cart_points(cart),
            "limit": POINTS_LIMIT,
            "total": session_store.cart_total_eur(cart),
            "currency": get_currency(),
            "reduction": get_reduction(),
        }
    )


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
    sessions_repo.save(sess["id"], user["id"], cart=cart)
    return jsonify(
        {
            "ok": True,
            "points": session_store.cart_points(cart),
            "limit": POINTS_LIMIT,
            "total": session_store.cart_total_eur(cart),
            "currency": get_currency(),
        }
    )


@app.route("/api/checkout", methods=["POST"])
@require_telegram_user
def api_checkout():
    """Valide le panier local : debit EUR + historique. Pas de commande KFC."""
    user = g.user
    sess = session_store.require_draft_session(user["id"])
    if not sess:
        return jsonify({"error": "Aucune session active"}), 400

    cart = list(sess.get("cart") or [])
    if not cart:
        return jsonify({"error": "Panier vide"}), 400

    for e in cart:
        if e.get("price") is None:
            return jsonify(
                {
                    "error": (
                        f"Article sans prix catalogue : "
                        f"{e.get('name') or e.get('itemId')}"
                    )
                }
            ), 409

    points_total = session_store.cart_points(cart)
    if points_total > POINTS_LIMIT:
        return jsonify(
            {"error": f"Panier a {points_total} points : limite de {POINTS_LIMIT} depassee."}
        ), 409

    total_eur = session_store.cart_total_eur(cart)
    balance = users_repo.get_balance(user["id"])
    if balance < total_eur:
        return jsonify(
            {
                "error": (
                    f"Solde insuffisant ({balance:.2f} EUR) "
                    f"pour un panier a {total_eur:.2f} EUR."
                ),
                "balance": balance,
                "total": total_eur,
            }
        ), 409

    if sess.get("status") != "DRAFT":
        return jsonify({"error": f"Checkout impossible (statut {sess.get('status')})."}), 409

    ok_debit, new_balance = users_repo.debit_if_sufficient(user["id"], total_eur)
    if not ok_debit:
        return jsonify(
            {
                "error": (
                    f"Debit solde impossible "
                    f"(solde {new_balance:.2f} EUR, total {total_eur:.2f} EUR)."
                ),
                "balance": new_balance,
                "total": total_eur,
            }
        ), 409

    order_uuid = str(uuid.uuid4())
    order_number = f"L-{order_uuid[:8].upper()}"
    snapshot = _order_payload(sess)

    try:
        order_history.save_submitted_order(
            order_uuid=order_uuid,
            order_number=order_number,
            confirmation_url="",
            store_id=sess.get("store_id"),
            store_name=sess.get("store_name"),
            store_city=sess.get("store_city"),
            total_points=points_total,
            total_eur=total_eur,
            account_id=None,
            user_id=user["id"],
            session_id=sess["id"],
            status="QUEUED",
            items=[
                {
                    "loyalty_id": e.get("itemId"),
                    "name": e.get("name"),
                    "cost": e.get("cost") or 0,
                    "quantity": e.get("quantity") or 1,
                    "modgrps": (e.get("kfc") or {}).get("modgrps") or [],
                }
                for e in cart
            ],
        )

        last_order = {
            "number": order_number,
            "uuid": order_uuid,
            "points": points_total,
            "total": total_eur,
            "confirmationUrl": None,
            "status": "QUEUED",
            "payload": snapshot,
        }
        sessions_repo.save(
            sess["id"],
            user["id"],
            status="CONFIRMED",
            cart=[],
            last_order=last_order,
            clear_basket=True,
        )
    except Exception:
        try:
            new_balance = users_repo.credit(user["id"], total_eur)
        except Exception:
            pass
        raise

    session_store.clear_menu_cache(sess["id"])

    return jsonify(
        {
            "orderNumber": order_number,
            "orderUUID": order_uuid,
            "points": points_total,
            "total": total_eur,
            "balance": new_balance,
            "currency": get_currency(),
            "confirmationUrl": None,
            "status": "QUEUED",
            "order": snapshot,
        }
    )


@app.route("/api/order-payload")
@require_telegram_user
def api_order_payload():
    user = g.user
    sess = session_store.require_open_session(user["id"])
    if not sess:
        return jsonify({})
    last = sess.get("last_order")
    payload = _order_payload(sess)
    if last:
        return jsonify({**payload, "lastOrder": last})
    return jsonify(payload)


@app.route("/api/checkin", methods=["POST"])
@require_telegram_user
def api_checkin():
    return jsonify(
        {
            "error": "Check-in KFC desactive — les commandes sont locales uniquement.",
            "code": "CHECKIN_DISABLED",
        }
    ), 410


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


@app.route("/api/admin/orders")
@require_telegram_user
def api_admin_orders():
    """File d'attente commandes en cours — admin uniquement."""
    user = g.user
    if not is_admin(user.get("telegram_id")):
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
    from db.repositories import orders as orders_repo

    return jsonify({"orders": orders_repo.list_queued_for_admin(limit=100)})


@app.route("/api/admin/orders/<int:order_id>")
@require_telegram_user
def api_admin_order_detail(order_id: int):
    user = g.user
    if not is_admin(user.get("telegram_id")):
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
    from db.repositories import orders as orders_repo

    order = orders_repo.get_order_by_id(order_id)
    if not order:
        return jsonify({"error": "Commande introuvable"}), 404
    return jsonify({"order": order})


@app.route("/api/admin/orders/<int:order_id>/user")
@require_telegram_user
def api_admin_order_user(order_id: int):
    user = g.user
    if not is_admin(user.get("telegram_id")):
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
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


@app.route("/api/admin/orders/<int:order_id>/complete", methods=["POST"])
@require_telegram_user
def api_admin_order_complete(order_id: int):
    user = g.user
    if not is_admin(user.get("telegram_id")):
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
    from db.repositories import orders as orders_repo
    from webapp import telegram as tg

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
    if client and client.get("telegram_id"):
        tg.send_message(
            int(client["telegram_id"]),
            "Votre commande est terminee, rendez vous dans « Ma commande » pour consulter.",
            parse_mode=None,
        )
    return jsonify({"order": order})


@app.route("/api/admin/orders/<int:order_id>/cancel", methods=["POST"])
@require_telegram_user
def api_admin_order_cancel(order_id: int):
    user = g.user
    if not is_admin(user.get("telegram_id")):
        return jsonify({"error": "Acces admin requis", "code": "ADMIN_ONLY"}), 403
    from db.repositories import orders as orders_repo
    from webapp import telegram as tg

    data = request.json or {}
    expl = str(data.get("explication") or "").strip()
    if not expl:
        return jsonify({"error": "Explication requise"}), 400

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
    if client and client.get("telegram_id"):
        msg = (
            "Votre commande a ete annulee.\n"
            f"Motif : {expl}\n"
        )
        if refund > 0:
            msg += f"Solde rembourse : {refund:.2f} {get_currency()}."
            if new_bal is not None:
                msg += f"\nNouveau solde : {new_bal:.2f} {get_currency()}."
        msg += "\nConsultez « Ma commande » pour le detail."
        tg.send_message(int(client["telegram_id"]), msg, parse_mode=None)

    return jsonify({"order": order, "refund": refund, "balance": new_bal})


@app.route("/api/ma-commande")
@require_telegram_user
def api_ma_commande():
    """Commande terminee du jour (visible jusqu'a minuit)."""
    user = g.user
    from db.repositories import orders as orders_repo

    order = orders_repo.get_ma_commande(user["id"])
    return jsonify({"order": order, "hasMaCommande": order is not None})


def _warm_cache():
    try:
        stores.GetAllStores()
    except Exception:
        pass


def main():
    try:
        ensure_database()
    except Exception as e:
        print(f"[-] PostgreSQL / migrations impossible : {e}")
        print("    Verifiez .env puis : python -m db.ensure_db")
        raise SystemExit(1)

    port = int(os.environ.get("PORT", "8080"))
    threading.Thread(target=_warm_cache, daemon=True).start()
    try:
        from webapp.bot_poll import start_polling_thread

        start_polling_thread()
    except Exception as e:
        print(f"[!] Poll Telegram ignore : {e}")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
