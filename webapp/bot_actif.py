"""Commande Telegram /actif — admin uniquement (ouvrir/fermer shop + prochaine heure)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Set

from kfc.config import (
    get_prochaine_heure,
    is_admin,
    is_shop_actif,
    set_prochaine_heure,
    set_shop_actif,
)
from webapp import telegram as tg

log = logging.getLogger(__name__)

# Chats admin en attente d'un texte « prochaine heure »
_awaiting_heure: Set[int] = set()


def _status_text() -> str:
    actif = is_shop_actif()
    etat = "ACTIF (ouvert)" if actif else "INACTIF (ferme)"
    lines = [
        "<b>Etat du shop</b>",
        f"Variable <code>actif</code> : <b>{etat}</b>",
    ]
    if not actif:
        heure = get_prochaine_heure()
        affichage = heure if heure else "aucune date fourni par l'admin"
        lines.append(f"Prochaine heure : <b>{affichage}</b>")
    else:
        lines.append("Prochaine heure : <i>(vide — shop actif)</i>")
    return "\n".join(lines)


def _keyboard() -> Dict[str, Any]:
    actif = is_shop_actif()
    rows = []
    if actif:
        rows.append(
            [{"text": "Passer en false (fermer)", "callback_data": "actif:set:0"}]
        )
    else:
        rows.append(
            [{"text": "Passer en true (ouvrir)", "callback_data": "actif:set:1"}]
        )
        rows.append(
            [{"text": "Prochaine heure", "callback_data": "actif:heure"}]
        )
    return {"inline_keyboard": rows}


def send_actif_panel(chat_id: int) -> None:
    tg.send_message(int(chat_id), _status_text(), reply_markup=_keyboard())


def handle_actif_command(message: Dict[str, Any]) -> bool:
    """Traite /actif. Retourne True si consomme."""
    text = (message.get("text") or "").strip()
    if not text.startswith("/actif"):
        return False
    # ignore /actif@BotName extras
    cmd = text.split()[0].split("@")[0]
    if cmd != "/actif":
        return False

    from_user = message.get("from") or {}
    tid = from_user.get("id")
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return True

    if not is_admin(tid):
        tg.send_message(int(chat_id), "Commande reservee a l'administrateur.")
        return True

    _awaiting_heure.discard(int(chat_id))
    send_actif_panel(int(chat_id))
    return True


def handle_actif_callback(cq: Dict[str, Any]) -> bool:
    """Traite callbacks actif:*. Retourne True si consomme."""
    data = (cq.get("data") or "").strip()
    if not data.startswith("actif:"):
        return False

    cq_id = cq.get("id")
    from_user = cq.get("from") or {}
    tid = from_user.get("id")
    message = cq.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")

    if not is_admin(tid):
        tg.answer_callback_query(
            cq_id, text="Reserve a l'administrateur.", show_alert=True
        )
        return True

    parts = data.split(":")
    try:
        if parts[1] == "set" and len(parts) >= 3:
            want = parts[2] == "1"
            set_shop_actif(want)
            tg.answer_callback_query(
                cq_id,
                text="Shop ouvert" if want else "Shop ferme",
            )
            if chat_id and message_id:
                tg.edit_message_text(
                    int(chat_id),
                    int(message_id),
                    _status_text(),
                    reply_markup=_keyboard(),
                )
            elif chat_id:
                send_actif_panel(int(chat_id))
            return True

        if parts[1] == "heure":
            if is_shop_actif():
                tg.answer_callback_query(
                    cq_id,
                    text="Impossible : le shop est actif.",
                    show_alert=True,
                )
                return True
            if chat_id is not None:
                _awaiting_heure.add(int(chat_id))
            tg.answer_callback_query(cq_id, text="Envoyez l'heure en texte")
            if chat_id is not None:
                tg.send_message(
                    int(chat_id),
                    "Envoyez maintenant la <b>prochaine heure d'activite</b> "
                    "(texte libre, ex. <code>demain 18h30</code>).",
                )
            return True
    except PermissionError as e:
        tg.answer_callback_query(cq_id, text=str(e), show_alert=True)
        return True
    except Exception:
        log.exception("Erreur callback /actif")
        tg.answer_callback_query(cq_id, text="Erreur", show_alert=True)
        return True

    tg.answer_callback_query(cq_id, text="Action inconnue")
    return True


def handle_actif_heure_message(message: Dict[str, Any]) -> bool:
    """Si admin attend une heure, enregistre le texte. Retourne True si consomme."""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None or int(chat_id) not in _awaiting_heure:
        return False

    from_user = message.get("from") or {}
    if not is_admin(from_user.get("id")):
        _awaiting_heure.discard(int(chat_id))
        return False

    text = (message.get("text") or "").strip()
    if not text or text.startswith("/"):
        return False

    _awaiting_heure.discard(int(chat_id))
    try:
        if is_shop_actif():
            tg.send_message(
                int(chat_id),
                "Impossible : le shop est actif. L'heure n'a pas ete enregistree.",
            )
            return True
        set_prochaine_heure(text)
        tg.send_message(
            int(chat_id),
            f"Prochaine heure enregistree : <b>{text}</b>",
        )
        send_actif_panel(int(chat_id))
    except PermissionError as e:
        tg.send_message(int(chat_id), str(e))
    except Exception:
        log.exception("Erreur set prochaine_heure")
        tg.send_message(int(chat_id), "Erreur lors de l'enregistrement.")
    return True


def process_update(update: Dict[str, Any]) -> bool:
    """Traite update /actif. True si consomme."""
    cq = update.get("callback_query")
    if cq and (cq.get("data") or "").startswith("actif:"):
        return handle_actif_callback(cq)

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return False
    if handle_actif_command(msg):
        return True
    if handle_actif_heure_message(msg):
        return True
    return False
