"""Telegram Bot API — envoi messages / photos (bot /actif, notifs user)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger(__name__)

API = "https://api.telegram.org"


def bot_token() -> str:
    return (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()


def _url(method: str) -> str:
    return f"{API}/bot{bot_token()}/{method}"


def api_call(method: str, *, files=None, **payload) -> Optional[Dict[str, Any]]:
    token = bot_token()
    if not token:
        log.warning("TELEGRAM_BOT_TOKEN manquant — envoi ignore (%s)", method)
        return None
    try:
        if files:
            r = requests.post(_url(method), data=payload, files=files, timeout=60)
        else:
            r = requests.post(_url(method), json=payload, timeout=30)
        data = r.json() if r.content else {}
        if not data.get("ok"):
            log.error("Telegram %s failed: %s", method, data)
            return None
        return data.get("result")
    except Exception as e:
        log.exception("Telegram %s error: %s", method, e)
        return None


def send_message(
    chat_id: int,
    text: str,
    *,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = "HTML",
    disable_web_page_preview: bool = True,
) -> Optional[Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "chat_id": int(chat_id),
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return api_call("sendMessage", **payload)


def send_photo(
    chat_id: int,
    path: str,
    *,
    caption: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(path):
        log.error("Photo introuvable: %s", path)
        return None
    data: Dict[str, Any] = {"chat_id": str(int(chat_id))}
    if caption:
        data["caption"] = caption[:1024]
    with open(path, "rb") as f:
        return api_call("sendPhoto", files={"photo": f}, **data)


def send_document(
    chat_id: int,
    path: str,
    *,
    caption: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(path):
        return None
    data: Dict[str, Any] = {"chat_id": str(int(chat_id))}
    if caption:
        data["caption"] = caption[:1024]
    with open(path, "rb") as f:
        return api_call(
            "sendDocument",
            files={"document": (os.path.basename(path), f)},
            **data,
        )


def send_media_group(chat_id: int, paths: List[str]) -> Optional[Any]:
    """Envoie jusqu'a 10 images en album. Retourne None si echec."""
    paths = [p for p in paths if os.path.isfile(p)][:10]
    if not paths:
        return None
    if len(paths) == 1:
        return send_photo(chat_id, paths[0])

    media = []
    files = {}
    for i, p in enumerate(paths):
        key = f"file{i}"
        media.append({"type": "photo", "media": f"attach://{key}"})
        files[key] = open(p, "rb")
    try:
        return api_call(
            "sendMediaGroup",
            files=files,
            chat_id=str(int(chat_id)),
            media=__import__("json").dumps(media),
        )
    finally:
        for f in files.values():
            try:
                f.close()
            except Exception:
                pass


def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
    *,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = "HTML",
) -> Optional[Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "chat_id": int(chat_id),
        "message_id": int(message_id),
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return api_call("editMessageText", **payload)


def answer_callback_query(
    callback_query_id: str,
    *,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> Optional[Dict[str, Any]]:
    payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
    if show_alert:
        payload["show_alert"] = True
    return api_call("answerCallbackQuery", **payload)


def get_updates(*, offset: Optional[int] = None, timeout: int = 25) -> List[Dict[str, Any]]:
    payload: Dict[str, Any] = {"timeout": int(timeout)}
    if offset is not None:
        payload["offset"] = int(offset)
    result = api_call("getUpdates", **payload)
    return result if isinstance(result, list) else []
