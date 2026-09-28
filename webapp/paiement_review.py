"""Review admin des recharges solde (accepter / refuser + notif user).

Plus de message Telegram admin : la file vit dans la mini-app (rubrique Paiement).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from db.repositories import paiements as paiements_repo
from db.repositories import users as users_repo
from kfc.config import get_currency
from webapp.bot_notify import notify_user

log = logging.getLogger(__name__)


def decide_paiement(
    demande_id: int, *, accept: bool
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    """Accepte ou refuse une demande PENDING.

    Retourne (payload_ok, error_message, http_status).
    """
    dem = paiements_repo.get_demande_by_id(demande_id)
    if not dem:
        return None, "demande introuvable", 404
    if dem["status"] != "PENDING":
        return None, f"statut {dem['status']} non traitable", 409

    user = users_repo.get_by_id(int(dem["userId"])) if dem.get("userId") else None
    if not user:
        return None, "user introuvable", 404

    cur = get_currency()
    montant = float(dem.get("montant") or 0)

    if accept:
        if montant <= 0:
            return None, "montant invalide", 400
        accepted = paiements_repo.accept_demande(demande_id)
        if not accepted:
            return None, "deja traitee", 409
        new_bal = users_repo.credit(int(user["id"]), montant)
        paiements_repo.add_user_paiement(
            int(user["id"]),
            solde=montant,
            moyen_paiement_id=dem.get("moyenId"),
            moyen=dem.get("moyenNom"),
        )
        notify_user(
            user.get("telegram_id"),
            (
                f"Paiement accepte.\n"
                f"Recharge de {montant:.2f} {cur} validee.\n"
                f"Nouveau solde : {new_bal:.2f} {cur}."
            ),
        )
        return (
            {"ok": True, "status": "ACCEPTED", "balance": new_bal, "montant": montant},
            None,
            200,
        )

    rejected = paiements_repo.reject_demande(demande_id)
    if not rejected:
        return None, "deja traitee", 409
    notify_user(
        user.get("telegram_id"),
        (
            "Paiement refuse.\n"
            "Votre demande de recharge a ete refusee. "
            "Aucun solde n'a ete ajoute."
        ),
    )
    return {"ok": True, "status": "REJECTED"}, None, 200
