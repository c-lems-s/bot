from .kfc_api import baskets, orders, users, braze
from .account import GetUserInfo, SubmitBasket
from .basket import GetBasketById
from .config import get_recaptcha_token, analytics_enabled
from .recaptcha import GetRecaptchaToken


def CheckoutBasket(basketUUID: str, userToken: str = None):
    """Passe le panier en checkout (équivalent du clic "Commander")."""
    basketJson = GetBasketById(basketUUID)
    if basketJson is None:
        print("[-] GetBasket Error")
        return None

    itemNumber = len(basketJson["items"])
    orderTotalPrice = basketJson["total"]

    users.SendUILog(
        f"UI - Checkout Page viewed for basket ID {basketUUID} , items in basket- {itemNumber} order total - {orderTotalPrice}",
        userToken,
    )

    if analytics_enabled():
        braze.SendBrazeEventSS()

    return True


def _resolve_recaptcha_token() -> str:
    """Jeton reCAPTCHA : bypass auto d'abord, puis fallback table config."""
    token = GetRecaptchaToken()
    if token and str(token).strip():
        return str(token).strip()

    fallback = get_recaptcha_token()
    if fallback and str(fallback).strip():
        print("[i] Bypass reCAPTCHA échoué — utilisation de recaptcha_token (config).")
        return str(fallback).strip()

    return ""


def SubmitOrder(basketUUID, basketItems, userUUID, userToken=None):
    """Soumet le panier (crée la commande).

    Le jeton reCAPTCHA est obtenu via bypass automatique (comme Click).
    Si le bypass échoue, repli sur recaptcha_token dans la table config.

    Returns:
        (orderUUID, orderNumber) ou (None, None) en cas d'erreur.
    """
    User = GetUserInfo(userUUID, userToken)
    if User is None:
        print("[-] GetUserInfo Error")
        return None, None

    userId = User["id"]
    firstName = User["firstName"]
    lastName = User["lastName"]
    phoneNumber = User["phoneNumber"]
    email = User["email"]

    users.SendUILog(f"UI - Order submission started for the basket id - {basketUUID}", userToken)

    code = baskets.AssociateToAccount(basketUUID, userId, firstName, lastName, phoneNumber, email)
    if code is None:
        print("[-] AssociateToAccount Error")
        return None, None

    recaptchaToken = _resolve_recaptcha_token()
    if not recaptchaToken:
        print(
            "[-] Token reCAPTCHA non obtenu (bypass échoué et recaptcha_token vide dans config)."
        )
        return None, None

    OrderInfo = SubmitBasket(userUUID, basketUUID, firstName, lastName, phoneNumber, email, recaptchaToken, userToken)
    if OrderInfo is None:
        print("[-] SubmitBasket Error")
        return None, None

    orderNumber = OrderInfo["orderNumber"]
    orderUUID = OrderInfo["orderIdTracker"]

    users.SendUILog(
        f"UI - Submit Order- Order submitted successfully for basket id -{basketUUID} , OrderTrackerNumber - {orderNumber}",
        userToken,
    )
    users.SendUILog(f"UI - Order Confirmation paged viewed for Order hash - {orderUUID}", userToken)

    if analytics_enabled():
        basket = GetBasketById(basketUUID)
        if basket is not None:
            braze.SendBrazeEventCommandComplete(basket["storeName"], basketItems)

    return orderUUID, orderNumber


def CheckinOrder(orderUUID, userToken=None):
    """Check-in de la commande (équivalent "Je suis là")."""
    Order = orders.GetOrder(orderUUID)
    if Order is None:
        print("[-] GetOrder Error")
        return None

    users.SendUILog(f"UI - Checkin process started for Order Id {orderUUID}", userToken)

    canCheckin = "true" if Order["checkin"]["possible"] else "false"
    users.SendUILog(
        f"UI - Validating if checkin possible for Order Id {orderUUID} , status - {canCheckin}",
        userToken,
    )

    code = orders.SendCheckin(orderUUID, userToken)
    if code is None:
        print("[-] SendCheckin Error")
        return None

    users.SendUILog(f"UI - Checkin successful for Order Id - {orderUUID}", userToken)

    if analytics_enabled():
        braze.SendBrazeCheckin()

    return True
