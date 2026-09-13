"""
Outil personnel de commande KFC (mono-compte).

Parcours :
    1. Recherche d'un resto KFC
    2. Choix des articles (avec options : boisson, frite, sauce...)
    3. Recapitulatif du panier
    4. Validation de la commande (avec VOTRE compte / VOS points)

Le reCAPTCHA de soumission est obtenu automatiquement (bypass), avec
repli eventuel sur recaptcha_token dans la table Postgres `config`.

Identifiants KFC : table `config` (plus de fichier au runtime).
Import one-shot : python -m db.seed_config
"""

import sys

from kfc import basket, cities, loyalty, modgrps, order, store_blacklist
from kfc.config import get_account_id, load_config
from kfc.loyalty import LOYALTY_MATCH_MIN, IsStoreEligible


def choisir_resto():
    """Etape 1 : recherche et selection d'un resto."""
    while True:
        place = input("\nVille / nom du resto > ").strip()
        if not place:
            continue

        matched = cities.SearchStores(place)
        if matched is None:
            print("[-] Aucun KFC trouve, reessayez.")
            continue

        blocked = store_blacklist.get_blacklisted_ids()
        print()
        for i, (name, city, _id) in enumerate(matched):
            flag = " [KFC indisponible]" if str(_id) in blocked else ""
            print(f"{i + 1}) {name} | {city}{flag}")

        raw = input(
            "\nChoix du resto (numero, ou 'r' pour rechercher a nouveau) > "
        ).strip()
        if raw.lower() == "r":
            continue

        try:
            idx = int(raw) - 1
            name, city, storeId = matched[idx]
        except (ValueError, IndexError):
            print("[-] Choix invalide.")
            continue

        if store_blacklist.is_blacklisted(storeId):
            print("[-] KFC indisponible (blacklist). Choisissez un autre restaurant.")
            continue

        print(f"[+] Resto selectionne : {name} | {city}")
        return name, city, storeId


def ajouter_articles(basketId, loyaltyMenu):
    """Etape 2 : ajout d'articles fidelite au panier KFC."""
    items = []
    while True:
        food = loyalty.ChooseLoyalty(loyaltyMenu)
        mods = []
        if food.get("modgrps"):
            mods = modgrps.ChooseModifications(food["modgrps"])

        result = basket.AddLoyaltyItemToBasket(
            basketId, food["id"], food["cost"], 1, modgrps=mods
        )
        if result is None:
            print("[-] Impossible d'ajouter l'article.")
        else:
            entry = dict(food)
            entry["quantity"] = 1
            entry["modgrps"] = mods
            items.append(entry)
            print(f"[+] Ajoute : {food['name']} ({food['cost']} pts)")

        again = input("\nAjouter un autre article ? [O/N] ").strip().lower()
        if again != "o":
            break
    return items


def afficher_panier(basketId):
    """Etape 3 : affiche le panier KFC courant."""
    data = basket.GetBasketById(basketId)
    if data is None:
        print("[-] Impossible de lire le panier.")
        return None

    print("\n=== Panier ===")
    for it in data.get("items") or []:
        name = it.get("name") or it.get("id") or "?"
        pts = it.get("loyaltyPoints") or it.get("points") or "?"
        print(f" - {name} ({pts} pts)")
    total = data.get("total")
    if total is not None:
        print(f"Total panier (API) : {total}")
    return data


def valider_commande(basketId, items, accountId, store_meta=None):
    """Etape 4 : checkout + soumission + check-in."""
    store_meta = store_meta or {}
    if order.CheckoutBasket(basketId, None) is None:
        print("[-] Erreur au checkout.")
        return

    print("[+] Checkout OK.")

    orderUUID, orderNumber = order.SubmitOrder(basketId, items, accountId, None)
    if orderUUID is None:
        print("[-] Erreur a la soumission de la commande.")
        return

    print(f"[+] Commande soumise ! Suivi web : {orderUUID}")
    confirmation_url = f"https://www.kfc.fr/confirmation-de-commande/{orderUUID}"
    points_total = sum(int(it.get("cost") or 0) for it in items)

    from db import history as order_history

    order_history.save_submitted_order(
        order_uuid=str(orderUUID),
        order_number=str(orderNumber),
        confirmation_url=confirmation_url,
        store_id=store_meta.get("store_id"),
        store_name=store_meta.get("store_name"),
        store_city=store_meta.get("store_city"),
        total_points=points_total,
        account_id=accountId,
        items=[
            {
                "loyalty_id": it.get("id"),
                "name": it.get("name"),
                "cost": it.get("cost") or 0,
                "quantity": it.get("quantity") or 1,
                "modgrps": it.get("modgrps") or [],
            }
            for it in items
        ],
    )

    print("\nLe check-in declenchera reellement la preparation (utilise vos points).")
    if input("Confirmer le check-in ? [O/N] ").strip().lower() != "o":
        print("[i] Check-in annule. La commande reste soumise mais non declenchee.")
        return

    if order.CheckinOrder(orderUUID, None) is None:
        print("[-] Erreur au check-in.")
        return

    order_history.mark_checked_in(str(orderUUID))
    print(f"[+] Commande confirmee ! Numero : {orderNumber}")
    print("    Vous pouvez aller recuperer votre commande.")


def main():
    try:
        from db.ensure_db import ensure_database

        ensure_database()
    except Exception as e:
        print(f"[-] Connexion PostgreSQL impossible : {e}")
        print("    Verifiez .env puis : python -m db.ensure_db")
        sys.exit(1)

    try:
        load_config(force=True)
    except RuntimeError as e:
        print(f"[-] {e}")
        sys.exit(1)

    accountId = get_account_id()
    if not accountId or accountId.startswith("VOTRE"):
        print("[-] account_id non renseigne dans la table config.")
        print("    SQL ou : python -m db.seed_config --force")
        sys.exit(1)

    while True:
        resto = choisir_resto()
        if resto is None:
            return
        name, city, storeId = resto

        menu = loyalty.GetLoyaltyMenu(accountId, storeId, None)
        if menu is None:
            print("[-] Impossible de recuperer le menu fidelite.")
            return

        loyaltyMenu, matched = menu
        if not IsStoreEligible(matched):
            store_blacklist.add_store(
                storeId,
                name=name,
                city=city,
                matched_items=matched,
                reason="loyalty_match",
            )
            print(
                f"[-] KFC indisponible ({matched} items, min {LOYALTY_MATCH_MIN}). "
                "Ajoute a la blacklist."
            )
            continue

        break

    basketId = basket.NewBasket(storeId)
    if basketId is None:
        print("[-] Impossible de creer le panier.")
        return

    items = ajouter_articles(basketId, loyaltyMenu)
    if not items:
        print("[-] Panier vide.")
        return

    if afficher_panier(basketId) is None:
        return

    if input("\nValider cette commande ? [O/N] ").strip().lower() != "o":
        print("[i] Commande annulee.")
        return

    valider_commande(
        basketId,
        items,
        accountId,
        store_meta={"store_id": storeId, "store_name": name, "store_city": city},
    )


if __name__ == "__main__":
    main()
