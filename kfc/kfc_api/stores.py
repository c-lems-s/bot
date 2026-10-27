import json
import time

from .helper import HTTPGet

_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "fr,fr-FR;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "cache-control": "no-cache",
    "origin": "https://www.kfc.fr",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0"
    ),
}

# Cache mémoire de la liste complète des restos (endpoint lourd et lent).
_ALL_STORES_CACHE = {"data": None, "ts": 0.0}
_ALL_STORES_TTL = 600  # 10 minutes


def _decode_json(response):
    """Décode le corps JSON en gérant l'encodage (UTF-8 puis Windows-1252).

    L'API renvoie certains accents en Windows-1252 : un décodage UTF-8 strict
    échoue alors, on bascule sur Windows-1252 pour éviter les caractères '?'.
    """
    raw = response.content
    for enc in ("utf-8", "windows-1252", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("utf-8", errors="replace"))


def GetAllStores(force: bool = False, retries: int = 3):
    """Liste complète des restos, avec cache mémoire et retries.

    L'endpoint est volumineux (400+ restos) et parfois lent : on met le
    résultat en cache pendant _ALL_STORES_TTL secondes.
    """
    now = time.time()
    cache = _ALL_STORES_CACHE
    if not force and cache["data"] is not None and (now - cache["ts"]) < _ALL_STORES_TTL:
        return cache["data"]

    url = "https://api.kfc.fr/stores/allStores"
    last_err = None
    for attempt in range(retries):
        r, c = HTTPGet(url, headers=_HEADERS, timeout=30)
        if r is not None:
            data = _decode_json(r)
            cache["data"] = data
            cache["ts"] = time.time()
            return data
        last_err = c
        time.sleep(1.5 * (attempt + 1))

    # Échec réseau : on renvoie le cache périmé s'il existe, sinon None.
    if cache["data"] is not None:
        return cache["data"]
    print(f"[-] GetAllStores échec : {last_err}")
    return None


def GetStoreMenu(storeId):
    url = f"https://api.kfc.fr/menu/{storeId}-pickup-menu"
    r, c = HTTPGet(url, headers=_HEADERS, timeout=30)
    if r is None:
        print(f"[-] {c}")
        return None
    return _decode_json(r)
