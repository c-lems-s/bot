"""Review admin des recharges solde (Telegram: notif + accepter/refuser)."""

from __future__ import annotations

import html
import logging
import os
from typing import Any, Dict, List, Optional

from db.repositories import paiements as paiements_repo
from db.repositories import users as users_repo
from kfc.config import get_admin, get_currency
from webapp import telegram as tg

log = logging.getLogger(__name__)

UPLOADS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "uploads", "paiements"
)


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=False)


def _fmt_dt(value: Any) -> str:
    if value is None:
        return "—"
    if hasattr(value, "isoformat"):
        return value.isoformat().replace("T", " ")[:19]
    s = str(value).strip()
    if not s:
        return "—"
    return s.replace("T", " ")[:19]


def build_admin_text(
    demande: Dict[str, Any], user: Dict[str, Any], stats: Dict[str, Any]
) -> str:
    cur = get_currency()
    uname = user.get("username")
    uname_s = f"@{uname}" if uname else "—"
    montant = float(demande.get("montant") or 0)
    bal = float(user.get("balance") or 0)
    bal_s = f"{bal:.2f}"
    montant_s = f"{montant:.2f}"
    lines = [
        "<b>Nouvelle demande de paiement</b>",
        f"Demande <code>#{demande['id']}</code> — statut PENDING",
        "",
        "<b>Utilisateur</b>",
        f"• id DB : <code>{_esc(user.get('id'))}</code>",
        f"• telegram_id : <code>{_esc(user.get('telegram_id'))}</code>",
        f"• username : {_esc(uname_s)}",
        f"• prenom : {_esc(user.get('first_name') or '—')}",
        f"• nom : {_esc(user.get('last_name') or '—')}",
        f"• langue : {_esc(user.get('language_code') or '—')}",
        f"• solde actuel : <b>{_esc(bal_s)} {_esc(cur)}</b>",
        f"• actif : {_esc(user.get('is_active'))}",
        f"• 1ere visite : {_esc(_fmt_dt(user.get('first_seen_at')))}",
        f"• derniere visite : {_esc(_fmt_dt(user.get('last_seen_at')))}",
        f"• nombre d'achats : <b>{_esc(stats.get('purchaseCount') or 0)}</b>",
        f"• dernier achat : {_esc(_fmt_dt(stats.get('lastPurchaseAt')))}",
        "",
        "<b>Commande / recharge detaillee</b>",
        f"• moyen : {_esc(demande.get('moyenNom') or '—')}",
        f"• lien : {_esc(demande.get('lien') or '—')}",
        f"• montant declare : <b>{_esc(montant_s)} {_esc(cur)}</b>",
        f"• preuves : {_esc(demande.get('preuveCount') or 0)}",
        f"• finalise le : {_esc(_fmt_dt(demande.get('finalizedAt')))}",
        "",
        "Les captures d'ecran suivent ci-dessous.",
        "Choisissez une action :",
    ]
    return "\n".join(lines)


def _review_keyboard(demande_id: int) -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Accepter",
                    "callback_data": f"pay:ok:{int(demande_id)}",
                },
                {
                    "text": "❌ Refuser",
                    "callback_data": f"pay:no:{int(demande_id)}",
                },
            ]
        ]
    }


def _preuve_paths(demande_id: int) -> List[str]:
    paths = []
    for p in paiements_repo.list_preuves(demande_id):
        stored = p.get("storedName") or ""
        if not stored:
            continue
        full = os.path.join(UPLOADS_DIR, str(demande_id), stored)
        if os.path.isfile(full):
            paths.append(full)
    return paths


def notify_admin_paiement(demande_id: int) -> bool:
    """Apres finalisation : message admin + preuves + boutons."""
    admin_id = get_admin()
    if not admin_id:
        log.error("config.admin manquant — notif paiement ignoree")
        return False

    dem = paiements_repo.get_demande_by_id(demande_id)
    if not dem or dem["status"] != "PENDING":
        return False

    user = users_repo.get_by_id(dem["userId"])
    if not user:
        log.error("User %s introuvable pour demande %s", dem["userId"], demande_id)
        return False

    stats = users_repo.get_purchase_stats(dem["userId"])
    text = build_admin_text(dem, user, stats)
    msg = tg.send_message(
        int(admin_id),
        text,
        reply_markup=_review_keyboard(demande_id),
    )
    if not msg:
        return False

    chat_id = (msg.get("chat") or {}).get("id") or admin_id
    message_id = msg.get("message_id")
    if message_id:
        paiements_repo.set_admin_message(demande_id, int(chat_id), int(message_id))

    paths = _preuve_paths(demande_id)
    if paths:
        sent = tg.send_media_group(int(admin_id), paths)
        if not sent:
            for i, path in enumerate(paths):
                if path.lower().endswith(".pdf"):
                    tg.send_document(int(admin_id), path, caption=f"Preuve {i + 1}")
                else:
                    tg.send_photo(int(admin_id), path, caption=f"Preuve {i + 1}")
    return True


def _notify_user(telegram_id: int, text: str) -> None:
    tg.send_message(int(telegram_id), text, parse_mode="HTML")


def handle_callback_query(cq: Dict[str, Any]) -> None:
    """Traite callback_data pay:ok:ID / pay:no:ID (admin uniquement)."""
    cq_id = cq.get("id")
    data = (cq.get("data") or "").strip()
    from_user = cq.get("from") or {}
    from_tid = from_user.get("id")
    message = cq.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")

    admin_id = get_admin()
    if not admin_id or from_tid is None or int(from_tid) != int(admin_id):
        tg.answer_callback_query(
            cq_id, text="Action reservee a l'administrateur.", show_alert=True
        )
        return

    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "pay" or parts[1] not in ("ok", "no"):
        tg.answer_callback_query(cq_id, text="Callback inconnu")
        return

    try:
        demande_id = int(parts[2])
    except ValueError:
        tg.answer_callback_query(cq_id, text="ID invalide")
        return

    dem = paiements_repo.get_demande_by_id(demande_id)
    if not dem:
        tg.answer_callback_query(cq_id, text="Demande introuvable", show_alert=True)
        return
    if dem["status"] != "PENDING":
        tg.answer_callback_query(
            cq_id, text=f"Deja traitee ({dem['status']})", show_alert=True
        )
        return

    user = users_repo.get_by_id(dem["userId"])
    if not user:
        tg.answer_callback_query(cq_id, text="User introuvable", show_alert=True)
        return

    cur = get_currency()
    montant = float(dem.get("montant") or 0)

    if parts[1] == "ok":
        if montant <= 0:
            tg.answer_callback_query(
                cq_id, text="Montant invalide sur la demande", show_alert=True
            )
            return
        accepted = paiements_repo.accept_demande(demande_id)
        if not accepted:
            tg.answer_callback_query(cq_id, text="Deja traitee", show_alert=True)
            return
        new_bal = users_repo.credit(user["id"], montant)
        paiements_repo.add_user_paiement(
            user["id"],
            solde=montant,
            moyen_paiement_id=dem.get("moyenId"),
            moyen=dem.get("moyenNom"),
        )
        _notify_user(
            int(user["telegram_id"]),
            (
                f"✅ <b>Paiement accepte</b>\n"
                f"Votre recharge de <b>{montant:.2f} {html.escape(cur)}</b> "
                f"a ete validee.\n"
                f"Nouveau solde : <b>{new_bal:.2f} {html.escape(cur)}</b>."
            ),
        )
        tg.answer_callback_query(cq_id, text="Solde credite")
        status_line = (
            f"\n\n✅ <b>ACCEPTE</b> — +{montant:.2f} {html.escape(cur)} "
            f"(solde user {new_bal:.2f})"
        )
    else:
        rejected = paiements_repo.reject_demande(demande_id)
        if not rejected:
            tg.answer_callback_query(cq_id, text="Deja traitee", show_alert=True)
            return
        _notify_user(
            int(user["telegram_id"]),
            (
                "❌ <b>Paiement refuse</b>\n"
                "Votre demande de recharge a ete refusee par un administrateur. "
                "Aucun solde n'a ete ajoute. Contactez le SAV si besoin."
            ),
        )
        tg.answer_callback_query(cq_id, text="Demande refusee")
        status_line = "\n\n❌ <b>REFUSE</b> — aucun solde ajoute"

    old_text = message.get("text") or message.get("caption") or ""
    if chat_id and message_id:
        new_text = (old_text + status_line) if old_text else status_line.strip()
        tg.edit_message_text(
            int(chat_id),
            int(message_id),
            new_text[:4000],
            reply_markup={"inline_keyboard": []},
        )


def process_update(update: Dict[str, Any]) -> None:
    cq = update.get("callback_query")
    if cq:
        try:
            handle_callback_query(cq)
        except Exception:
            log.exception("Erreur callback paiement")
