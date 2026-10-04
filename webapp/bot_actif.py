"""Commande Telegram /actif — admin uniquement (ouvrir/fermer shop + prochaine heure)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from kfc.config import (
    clear_cache,
    get_prochaine_heure,
    is_admin,
    is_shop_actif,
    set_prochaine_heure,
    set_shop_actif,
)
from webapp import telegram as tg

log = logging.getLogger(__name__)

# Marqueur dans le message ForceReply — detecte sur n'importe quel worker.
_HEURE_MARKER = "#actif_heure"
_HEURE_PROMPT = (
    "Envoyez maintenant la <b>prochaine heure d'activite</b> "
    "(texte libre, ex. <code>demain 18h30</code>).\n"
    f"<code>{_HEURE_MARKER}</code>"
)


def _refresh_config() -> None:
    """Force une lecture DB fraiche (multi-workers gunicorn)."""
    clear_cache()


def _status_text() -> str:
    _refresh_config()
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
    _refresh_config()
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


def _refresh_panel(
    chat_id: Optional[int],
    message_id: Optional[int],
) -> None:
    """Met a jour le message du panel ; si edit echoue → nouveau message."""
    if chat_id is None:
        return
    text = _status_text()
    markup = _keyboard()
    if message_id is not None:
        edited = tg.edit_message_text(
            int(chat_id),
            int(message_id),
            text,
            reply_markup=markup,
        )
        if edited is not None:
            return
        log.warning(
            "editMessageText /actif echoue — renvoi d'un nouveau panel (chat=%s)",
            chat_id,
        )
    send_actif_panel(int(chat_id))


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

    _refresh_config()
    if not is_admin(tid):
        tg.send_message(int(chat_id), "Commande reservee a l'administrateur.")
        return True

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

    _refresh_config()
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
            _refresh_config()
            tg.answer_callback_query(
                cq_id,
                text="Shop ouvert" if want else "Shop ferme",
            )
            _refresh_panel(
                int(chat_id) if chat_id is not None else None,
                int(message_id) if message_id is not None else None,
            )
            return True

        if parts[1] == "heure":
            if is_shop_actif():
                tg.answer_callback_query(
                    cq_id,
                    text="Impossible : le shop est actif.",
                    show_alert=True,
                )
                return True
            tg.answer_callback_query(cq_id, text="Envoyez l'heure en texte")
            if chat_id is not None:
                tg.send_message(
                    int(chat_id),
                    _HEURE_PROMPT,
                    reply_markup={
                        "force_reply": True,
                        "selective": True,
                        "input_field_placeholder": "ex. demain 18h30",
                    },
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


def _is_heure_reply(message: Dict[str, Any]) -> bool:
    """True si le message repond au prompt ForceReply #actif_heure."""
    reply = message.get("reply_to_message") or {}
    reply_text = reply.get("text") or ""
    reply_html = reply.get("caption") or ""
    blob = f"{reply_text}\n{reply_html}"
    return _HEURE_MARKER in blob or "prochaine heure d'activite" in blob.lower()


def handle_actif_heure_message(message: Dict[str, Any]) -> bool:
    """Enregistre l'heure si reply au prompt admin. True si consomme."""
    if not _is_heure_reply(message):
        return False

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return False

    from_user = message.get("from") or {}
    _refresh_config()
    if not is_admin(from_user.get("id")):
        return False

    text = (message.get("text") or "").strip()
    if not text or text.startswith("/"):
        return False
    # Ne pas enregistrer le marqueur lui-meme
    if text == _HEURE_MARKER:
        return False

    try:
        if is_shop_actif():
            tg.send_message(
                int(chat_id),
                "Impossible : le shop est actif. L'heure n'a pas ete enregistree.",
            )
            return True
        set_prochaine_heure(text)
        _refresh_config()
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
