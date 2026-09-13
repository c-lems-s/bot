import unicodedata

from .kfc_api import stores


def RemoveAccents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def GetMatchingPlace(allStores, place):
    """Retourne la liste des restos correspondant au texte saisi.

    Recherche sur le nom, la ville, l'adresse et le code postal.
    Chaque élément est un tuple (name, city, id).
    """
    matched = []
    lowerPlace = RemoveAccents(place.lower()).strip()
    for store in allStores:
        storeName = RemoveAccents(str(store.get("name", "")).lower())
        storeCity = RemoveAccents(str(store.get("city", "")).lower())
        storeAddress = RemoveAccents(str(store.get("address", "")).lower())
        storePost = str(store.get("postCode", "")).lower()
        if (
            lowerPlace in storeName
            or lowerPlace in storeCity
            or lowerPlace in storeAddress
            or lowerPlace in storePost
        ):
            matched.append((store["name"], store["city"], store["id"]))

    if len(matched) <= 0:
        return None
    return matched


def SearchStores(place: str):
    """Recherche des restos KFC à partir d'un texte (ville, nom, adresse).

    Returns:
        list[tuple[str, str, str]] | None : liste (name, city, id) ou None.
    """
    allStores = stores.GetAllStores()
    if allStores is None:
        return None
    return GetMatchingPlace(allStores, place)
