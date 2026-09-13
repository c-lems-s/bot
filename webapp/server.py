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

from kfc import basket, cities, loyalty, order  # noqa: E402
from kfc.kfc_api import stores  # noqa: E402
from kfc.config import get_account_id, get_currency  # noqa: E402
from kfc import store_blacklist  # noqa: E402
from kfc.loyalty import LOYALTY_MATCH_MIN, IsStoreEligible  # noqa: E402
from db import history as order_history  # noqa: E402
from db.ensure_db import ensure_database  # noqa: E402
from db.repositories import articles as articles_repo  # noqa: E402
from db.repositories import sessions as sessions_repo  # noqa: E402
from db.repositories import users as users_repo  # noqa: E402
from webapp.auth import require_telegram_user  # noqa: E402
from webapp import session_store  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=None)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def _no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


POINTS_LIMIT = 2500
SOON_LABEL = "Bientôt disponible"


def _account_configured():
    try:
        account = get_account_id()
    except RuntimeError:
        return False
    return bool(account) and not account.startswith("VOTRE")


def _build_loyalty_menu(loyaltyMenu, session_id: int):
    """Categories UI via article.label ; inconnus -> Bientot disponible."""
    menu_items = {}
    raw_items = []

    for items in loyaltyMenu.values():
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
            price = float(art["price"])
            available = True
        else:
            label = SOON_LABEL
            price = None
            available = False

        if label not in grouped:
            grouped[label] = []
            label_order.append(label)

        grouped[label].append(
            {
                "id": item_id,
                "name": it["name"],
                "cost": it.get("cost"),
                "price": price,
                "available": available,
                "image": it.get("image", ""),
                "hasOptions": "modgrps" in it,
            }
        )

    session_store.set_menu_items(session_id, menu_items)

    # Labels catalogue (alpha) puis Bientot disponible en dernier
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


def _extract_kfc_item_id(add_result, loyalty_id=None):
    if not isinstance(add_result, dict):
        return None
    items = add_result.get("items") or []
    if not items:
        return None
    last = items[-1]
    return last.get("id") or last.get("itemId") or last.get("basketItemId")


def _order_payload(sess):
    return {
        "storeId": sess.get("store_id"),
        "storeName": sess.get("store_name"),
        "basketId": sess.get("basket_id"),
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
    return jsonify(
        {
            "configured": _account_configured(),
            "balance": balance,
            "currency": get_currency(),
            "user": {
                "id": user["id"],
                "telegramId": user["telegram_id"],
                "username": user.get("username"),
                "firstName": user.get("first_name"),
            },
        }
    )


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

    loyaltyMenu = None
    connected = False
    basket_id = None
    matched_count = None

    if _account_configured():
        try:
            res = loyalty.GetLoyaltyMenu(get_account_id(), storeId, None)
        except Exception:
            res = None
        if res is not None:
            loyaltyMenu, matched_count = res[0], res[1]
            if not IsStoreEligible(matched_count):
                store_blacklist.add_store(
                    storeId,
                    name=name,
                    city=city,
                    matched_items=matched_count,
                    reason="loyalty_match",
                )
                return jsonify(
                    {
                        "error": "KFC indisponible",
                        "available": False,
                        "blacklisted": True,
                        "matchedItems": matched_count,
                        "requiredMin": LOYALTY_MATCH_MIN,
                    }
                ), 400

            connected = True
            basket_id = basket.NewBasket(storeId)
            if basket_id is None:
                return jsonify({"error": "Impossible de creer le panier KFC."}), 502

    if loyaltyMenu is None:
        loyaltyMenu = loyalty.GetStoreLoyaltyMenu(storeId)

    if loyaltyMenu is None:
        return jsonify({"error": "Menu fidelite indisponible pour ce restaurant."}), 502

    sess = sessions_repo.create_draft(
        user["id"],
        store_id=str(storeId),
        store_name=name,
        store_city=city,
        basket_id=basket_id,
    )
    categories = _build_loyalty_menu(loyaltyMenu, sess["id"])

    return jsonify(
        {
            "store": {"name": name, "city": city, "id": storeId},
            "categories": categories,
            "connected": connected,
            "liveOrdering": bool(basket_id),
            "matchedItems": matched_count,
            "available": True,
            "sessionId": sess["id"],
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
            "price": float(art["price"]),
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
        unit_price = float(art["price"])
    except (TypeError, ValueError):
        return jsonify({"error": "Prix article invalide en catalogue."}), 500

    cost = it.get("cost")
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

    kfc_item = {
        "id": it["id"],
        "unitPrice": 0,
        "quantity": 1,
        "modgrps": full_modgrps,
        "loyaltyItem": True,
        "loyaltyPoints": cost or 0,
    }

    kfc_item_id = None
    basket_id = sess.get("basket_id")

    if basket_id:
        if cost is None:
            return jsonify(
                {"error": "Cout en points inconnu — compte KFC requis."}
            ), 400
        result = basket.AddLoyaltyItemToBasket(
            basket_id, it["id"], cost, 1, modgrps=full_modgrps
        )
        if result is None:
            return jsonify({"error": "Impossible d'ajouter l'article au panier KFC."}), 502
        kfc_item_id = _extract_kfc_item_id(result)

    cart.append(
        {
            "uid": uuid.uuid4().hex,
            "kfcItemId": str(kfc_item_id) if kfc_item_id else None,
            "itemId": str(it["id"]),
            "name": it["name"],
            "image": it.get("image", ""),
            "options": options,
            "cost": cost,
            "price": unit_price,
            "quantity": 1,
            "kfc": kfc_item,
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
            "liveOrdering": bool(basket_id),
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
            "price": e.get("price"),
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

    basket_id = sess.get("basket_id")
    kfc_item_id = entry.get("kfcItemId")
    if basket_id and kfc_item_id:
        result = basket.RemoveLoyaltyItemFromBasket(basket_id, kfc_item_id)
        if result is None:
            return jsonify({"error": "Impossible de retirer l'article du panier KFC."}), 502

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

    basket_id = sess.get("basket_id")
    if not basket_id or not _account_configured():
        return jsonify(
            {
                "error": "Compte KFC non configure. Renseignez la table config "
                "(python -m db.seed_config) puis selectionnez a nouveau un restaurant."
            }
        ), 400

    if sess.get("status") != "DRAFT":
        return jsonify({"error": f"Checkout impossible (statut {sess.get('status')})."}), 409

    account_id = get_account_id()

    if order.CheckoutBasket(basket_id, None) is None:
        return jsonify({"error": "Echec du checkout KFC."}), 502

    basket_items = [
        {"name": e.get("name", ""), "quantity": e.get("quantity", 1)} for e in cart
    ]

    order_uuid, order_number = order.SubmitOrder(
        basket_id, basket_items, account_id, None
    )
    if order_uuid is None:
        return jsonify(
            {"error": "Echec de la soumission KFC (reCAPTCHA, reseau ou compte)."}
        ), 502

    ok_debit, new_balance = users_repo.debit_if_sufficient(user["id"], total_eur)
    if not ok_debit:
        return jsonify(
            {
                "error": (
                    "Commande KFC soumise mais debit solde impossible "
                    f"(solde {new_balance:.2f} EUR, total {total_eur:.2f} EUR)."
                ),
                "orderNumber": str(order_number),
                "orderUUID": str(order_uuid),
                "balance": new_balance,
                "total": total_eur,
            }
        ), 502

    confirmation_url = f"https://www.kfc.fr/confirmation-de-commande/{order_uuid}"
    snapshot = _order_payload(sess)

    order_history.save_submitted_order(
        order_uuid=str(order_uuid),
        order_number=str(order_number),
        confirmation_url=confirmation_url,
        store_id=sess.get("store_id"),
        store_name=sess.get("store_name"),
        store_city=sess.get("store_city"),
        total_points=points_total,
        account_id=account_id,
        user_id=user["id"],
        session_id=sess["id"],
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
        "number": str(order_number),
        "uuid": str(order_uuid),
        "points": points_total,
        "total": total_eur,
        "confirmationUrl": confirmation_url,
        "status": "SUBMITTED",
        "payload": snapshot,
    }
    sessions_repo.save(
        sess["id"],
        user["id"],
        status="SUBMITTED",
        cart=[],
        last_order=last_order,
        clear_basket=True,
    )
    session_store.clear_menu_cache(sess["id"])

    return jsonify(
        {
            "orderNumber": str(order_number),
            "orderUUID": str(order_uuid),
            "points": points_total,
            "total": total_eur,
            "balance": new_balance,
            "currency": get_currency(),
            "confirmationUrl": confirmation_url,
            "status": "SUBMITTED",
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
    user = g.user
    sess = session_store.require_open_session(user["id"])
    if not sess:
        return jsonify({"error": "Aucune commande a confirmer"}), 400

    last = sess.get("last_order") or {}
    if not last.get("uuid"):
        return jsonify({"error": "Aucune commande a confirmer"}), 400

    if sess.get("status") != "SUBMITTED":
        return jsonify(
            {"error": f"Check-in impossible (statut {sess.get('status')})."}
        ), 409

    if order.CheckinOrder(last["uuid"], None) is None:
        return jsonify(
            {"error": "Check-in KFC impossible (trop tot ou erreur API)."}
        ), 502

    order_history.mark_checked_in(last["uuid"])
    last = dict(last)
    last["status"] = "CHECKED_IN"
    sessions_repo.save(
        sess["id"], user["id"], status="CHECKED_IN", last_order=last
    )
    return jsonify(
        {
            "ok": True,
            "orderNumber": last.get("number"),
            "orderUUID": last.get("uuid"),
            "confirmationUrl": last.get("confirmationUrl"),
            "status": "CHECKED_IN",
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
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
