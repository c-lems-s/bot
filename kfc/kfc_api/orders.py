from .helper import HTTPGet, HTTPPost
from ..config import get_cookies, get_authorization


def SendCheckin(orderUUID: str, userToken=None):
    url = f"https://www.kfc.fr/api/order/{orderUUID}/checkin"

    headers = {
        "Host": "www.kfc.fr",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": f"https://www.kfc.fr/confirmation-de-commande/{orderUUID}",
        "Culturecode": "fr",
        "Content-Type": "application/json",
        "Authorization": get_authorization(),
        "Origin": "https://www.kfc.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Te": "trailers",
    }

    data = {"intent": "instore", "recaptchaToken": "", "posType": "Aloha"}

    r, c = HTTPPost(url, headers=headers, cookies=get_cookies(), json=data)
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()


def GetOrder(orderId: str):
    url = f"https://api.kfc.fr/orders/{orderId}"

    headers = {
        "Host": "api.kfc.fr",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.kfc.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Te": "trailers",
    }

    r, c = HTTPGet(url, headers=headers)
    if r is None:
        print(f"[-] {c}")
        return None
    return r.json()
