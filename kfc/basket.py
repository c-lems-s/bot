from .kfc_api import baskets
from typing import Optional


def NewBasket(storeId: str) -> Optional[str]:
    basket = baskets.CreateBasket(storeId)
    if basket is None:
        return None
    return basket["id"]


def GetBasketById(basketUUID: str) -> Optional[dict]:
    basket = baskets.GetBasketInfo(basketUUID)
    if basket is None:
        return None
    return basket


def AddLoyaltyItemToBasket(basketUUID: str, loyaltyId: str, loyaltyPrice: int, quantity: int, modgrps: list = None) -> Optional[dict]:
    r = baskets.AddLoyaltyItem(basketUUID, loyaltyId, loyaltyPrice, quantity, modgrps or [])
    if r is None:
        return None
    return r


def RemoveLoyaltyItemFromBasket(basketUUID: str, itemUUID: str) -> Optional[dict]:
    r = baskets.RemoveLoyaltyItem(basketUUID, itemUUID)
    if r is None:
        return None
    return r
