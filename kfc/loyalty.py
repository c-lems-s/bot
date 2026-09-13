from .kfc_api import stores
from .account import GetAccountLoyaltyInfo

# Seuil d'éligibilité (aligné Click : matched_count > 30).
LOYALTY_MATCH_MIN = 31


def _store_pos_id(product_item: dict) -> str:
    """Normalise posItemId (str ou dict aloha/amrest)."""
    pos_raw = product_item.get("posItemId", "")
    if isinstance(pos_raw, dict):
        return str(pos_raw.get("alohaItemId", "") or pos_raw.get("amrestItemId", "") or "")
    return str(pos_raw)


def LoyaltyMatch(loyaltyInfo, menuInfo):
    """Associe les récompenses fidélité du compte au menu du resto choisi."""
    res = {}
    n = 0
    for Group in loyaltyInfo:
        GroupItems = Group["items"]
        res[Group["name"]] = []

        for gi in GroupItems:
            alohaItemId = str(gi["itemId"]["alohaItemId"])
            amrestItemId = str(gi["itemId"]["amrestItemId"])

            StoreLoyaltyProducts = menuInfo["products"]
            StoreLoyaltyProducts_len = len(StoreLoyaltyProducts)

            k = 0
            while k < StoreLoyaltyProducts_len:
                store_pos = _store_pos_id(StoreLoyaltyProducts[k]["items"][0])
                if store_pos == alohaItemId or store_pos == amrestItemId:
                    break
                k += 1

            if k != StoreLoyaltyProducts_len:
                n += 1
                storeItem = StoreLoyaltyProducts[k]["items"][0]
                data = {
                    "name": storeItem["name"],
                    "id": storeItem["id"],
                    "cost": gi["points"],
                    "image": storeItem.get("imageName", ""),
                }
                if "modgrps" in storeItem.keys():
                    data["modgrps"] = storeItem["modgrps"]
                res[Group["name"]].append(data)

    return res, n


def IsStoreEligible(matched_count) -> bool:
    """True si le resto a assez d'articles fidélité matchés."""
    try:
        return matched_count is not None and int(matched_count) >= LOYALTY_MATCH_MIN
    except (TypeError, ValueError):
        return False


def GetStoreLoyaltyMatchCount(accountId: str, storeId: str, accountToken: str = None):
    """Nombre d'items fidélité matchés pour ce resto, ou None si erreur."""
    res = GetLoyaltyMenu(accountId, storeId, accountToken)
    if res is None:
        return None
    return res[1]


def GetLoyaltyFromStore(storeId: str):
    """Récupère la catégorie LOYALTY du menu du resto."""
    storeMenu = stores.GetStoreMenu(storeId)
    if storeMenu is None:
        return None

    categories = storeMenu["categories"][0]["categories"]
    for cat in categories:
        if cat["name"] == "LOYALTY":
            return cat
    return None


def GetLoyaltyMenu(accountId: str, storeId: str, accountToken: str = None):
    """Retourne le menu fidélité disponible dans le resto choisi.

    Returns:
        (loyaltyMenu, matchedItemCount) ou None si erreur.
    """
    loyaltyInfo = GetAccountLoyaltyInfo(accountId, accountToken)
    if loyaltyInfo is None:
        return None
    loyaltyInfo = loyaltyInfo["rewards"]

    storeLoyalty = GetLoyaltyFromStore(storeId)
    if storeLoyalty is None:
        return None

    loyaltyMenu, matchedItem = LoyaltyMatch(loyaltyInfo, storeLoyalty)
    return loyaltyMenu, matchedItem


def GetStoreLoyaltyMenu(storeId: str):
    """Menu fidélité PUBLIC du resto (sans compte, donc sans coût en points).

    Permet de visualiser les articles fidélité disponibles dans un resto sans
    être connecté. Le coût en points ('cost') vaut None car il dépend du compte.

    Returns:
        {nomCategorie: [ {name, id, cost=None, modgrps?}, ... ]} ou None.
    """
    cat = GetLoyaltyFromStore(storeId)
    if cat is None:
        return None

    items = []
    for product in cat.get("products", []):
        for it in product.get("items", []):
            data = {
                "name": it.get("name", "?"),
                "id": it.get("id"),
                "cost": None,
                "image": it.get("imageName", ""),
            }
            if it.get("modgrps"):
                data["modgrps"] = it["modgrps"]
            items.append(data)

    if not items:
        return None

    return {"Menu Fidélité": items}


def ChooseLoyalty(loyaltyMenu: dict) -> dict:
    """Sélection d'un produit fidélité (CLI)."""
    categories = list(loyaltyMenu.keys())

    print("\n=== Categories ===")
    for i, category in enumerate(categories):
        print(f"{i + 1}. {category}")

    cat_index = int(input("Select category: ")) - 1
    selected_category = categories[cat_index]

    items = loyaltyMenu[selected_category]

    print(f"\n=== {selected_category} ===")
    for i, item in enumerate(items):
        print(f"{i + 1}. {item['name']} ({item['cost']} pts)")

    item_index = int(input("Select item: ")) - 1
    selected_item = items[item_index]

    data = {
        "name": selected_item["name"],
        "id": selected_item["id"],
        "cost": selected_item["cost"],
    }
    if "modgrps" in selected_item.keys():
        data["modgrps"] = selected_item["modgrps"]

    return data
