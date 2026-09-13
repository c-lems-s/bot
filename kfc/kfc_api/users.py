from .helper import HTTPGet, HTTPPost
from ..config import get_cookies, get_authorization


def GetUserInfo(userUUID: str, userToken: str = None):
    url = f"https://www.kfc.fr/api/users/{userUUID}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.kfc.fr/paiement",
        "Culturecode": "fr",
        "Authorization": get_authorization(),
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=0",
        "Te": "trailers",
    }

    r, c = HTTPGet(url, headers=headers, cookies=get_cookies())
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()


def GetUserLoyaltyInfo(userUUID: str, userToken: str = None):
    url = f"https://www.kfc.fr/api/users/{userUUID}/loyaltyinfo"

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "fr,fr-FR;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Authorization": get_authorization(),
        "cache-control": "no-cache",
        "culturecode": "fr",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.kfc.fr/loyalty",
        "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0"
        ),
    }

    r, c = HTTPGet(url, headers=headers, cookies=get_cookies())
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()


def GetUserLoyaltyPointsExpireDateInfo(userUUID: str, userToken: str = None):
    url = f"https://www.kfc.fr/api/users/{userUUID}/loyaltypointexpiredate"

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "fr,fr-FR;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Authorization": get_authorization(),
        "cache-control": "no-cache",
        "culturecode": "fr",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.kfc.fr/loyalty",
        "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0"
        ),
    }

    r, c = HTTPGet(url, headers=headers, cookies=get_cookies())
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()


def SendUILog(message: str, userToken: str = None):
    url = "https://www.kfc.fr/api/uiloginfo"

    headers = {
        "Host": "www.kfc.fr",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.kfc.fr/paiement",
        "Culturecode": "fr",
        "Content-Type": "application/json",
        "Authorization": get_authorization(),
        "Origin": "https://www.kfc.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=0",
        "Te": "trailers",
    }

    payload = {"error": "Info", "message": message}

    r, c = HTTPPost(url, headers=headers, cookies=get_cookies(), json=payload)
    if r is None:
        return None
    return c


def RegisterBasket(userId: str, basketId: str, firstName, lastName, phoneNumber, email, recaptchaToken, userToken: str = None):
    url = f"https://www.kfc.fr/api/users/{userId}/baskets/{basketId}/registeredsubmit"

    headers = {
        "Host": "www.kfc.fr",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.kfc.fr/prise-de-commande",
        "Culturecode": "fr",
        "Content-Type": "application/json",
        "Authorization": get_authorization(),
        "Origin": "https://www.kfc.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Te": "trailers",
    }

    payload = {
        "customer": {
            "id": userId,
            "firstName": firstName,
            "lastName": lastName,
            "phoneNumber": phoneNumber,
            "email": email,
            "password": "",
        },
        "tender": "cash",
        "savedCardId": None,
        "deliveryAddress": None,
        "fulfillment": {
            "asap": True,
            "scheduled": {"date": "", "key": "", "time": ""},
        },
        "acceptTermConditions": True,
        "saveCard": False,
        "existingCard": False,
        "posType": "Aloha",
        "recaptchaToken": recaptchaToken,
    }

    r, c = HTTPPost(url, headers=headers, cookies=get_cookies(), json=payload)
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()
