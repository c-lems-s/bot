from .helper import HTTPGet, HTTPPost, HTTPPut

_JSON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "fr,fr-FR;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "cache-control": "no-cache",
    "content-type": "application/json",
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


def CreateBasket(storeId: str):
    url = "https://api.kfc.fr/baskets"

    payload = {
        "channel": "Web",
        "device": "Desktop",
        "storeId": storeId,
        "disposition": "pickup",
        "fulfillment": {"asap": True},
        "items": [],
    }

    r, c = HTTPPost(url, headers=_JSON_HEADERS, json=payload)
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()


def GetBasketInfo(basketUUID):
    url = f"https://api.kfc.fr/baskets/{basketUUID}"
    r, c = HTTPGet(url, headers=_JSON_HEADERS)
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()


def AddLoyaltyItem(basketUUID, loyaltyId: str, loyaltyPrice, quantity: int, modgrps=None):
    if modgrps is None:
        modgrps = []

    url = f"https://api.kfc.fr/baskets/{basketUUID}/items"

    data = [
        {
            "id": loyaltyId,
            "unitPrice": 0,
            "quantity": quantity,
            "modgrps": modgrps,
            "loyaltyItem": True,
            "loyaltyPoints": loyaltyPrice,
        }
    ]

    r, c = HTTPPost(url, headers=_JSON_HEADERS, json=data)
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()


def RemoveLoyaltyItem(basketUUID: str, itemId: str):
    url = f"https://api.kfc.fr/baskets/{basketUUID}/items/{itemId}"

    data = {"action": "update-quantity", "item": {"quantity": 0}}

    r, c = HTTPPut(url, headers=_JSON_HEADERS, json=data)
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()


def AssociateToAccount(basketUUID: str, userUUID: str, firstName: str, lastName: str, phoneNumber: str, email: str):
    url = f"https://api.kfc.fr/baskets/{basketUUID}"

    headers = {
        "Host": "api.kfc.fr",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "Origin": "https://www.kfc.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Priority": "u=0",
        "Te": "trailers",
    }

    payload = {
        "deliveryAddress": None,
        "customer": {
            "id": userUUID,
            "firstName": firstName,
            "lastName": lastName,
            "phoneNumber": phoneNumber,
            "email": email,
            "password": "",
        },
        "tender": "cash",
    }

    r, c = HTTPPut(url, headers=headers, json=payload)
    if r is None:
        print(f"[-] {c}")
        return None
    return c
