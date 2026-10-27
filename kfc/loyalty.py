from .kfc_api import stores


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
