from .kfc_api import users
from typing import Optional


def GetAccountLoyaltyInfo(userUUID: str, userToken: str = None) -> Optional[dict]:
    loyaltyInfo = users.GetUserLoyaltyInfo(userUUID, userToken)
    if loyaltyInfo is None:
        return None
    return loyaltyInfo


def GetUserLoyaltyPointsExpireDateInfo(userUUID: str, userToken: str = None) -> Optional[dict]:
    loyaltyInfo = users.GetUserLoyaltyPointsExpireDateInfo(userUUID, userToken)
    if loyaltyInfo is None:
        return None
    return loyaltyInfo


def GetUserInfo(userUUID: str, userToken: str = None) -> Optional[dict]:
    userInfo = users.GetUserInfo(userUUID, userToken)
    if userInfo is None:
        return None
    return userInfo


def SubmitBasket(userUUID: str, basketUUID: str, firstName: str, lastName: str, phoneNumber: str, email: str, recaptchaToken: str, userToken: str = None) -> Optional[dict]:
    orderInfo = users.RegisterBasket(userUUID, basketUUID, firstName, lastName, phoneNumber, email, recaptchaToken, userToken)
    if orderInfo is None:
        return None
    return orderInfo


def SendUILog(message: str, userToken: str = None) -> Optional[int]:
    c = users.SendUILog(message, userToken)
    if c is None:
        return None
    return c
