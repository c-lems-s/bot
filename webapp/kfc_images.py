"""Proxy / cache des images produit KFC (static.kfc.fr).

Les Mini Apps Telegram chargent mal les hotlinks CDN (Referer, lazy-load).
On sert les images en same-origin : ``/api/kfc-image/<name>``.
"""

from __future__ import annotations

import re
import time
from typing import Dict, Optional, Tuple

import requests

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
_SIZES = ("xs", "sm", "md", "lg")
_EXTS = (".jpg", ".jpeg", ".png", ".webp")
_BASE = "https://static.kfc.fr/images/items"
_HEADERS = {
    "accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "accept-language": "fr-FR,fr;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "referer": "https://www.kfc.fr/",
    "origin": "https://www.kfc.fr",
}

# cache memoire leger : name -> (expires_ts, content_type, body)
_CACHE: Dict[str, Tuple[float, str, bytes]] = {}
_CACHE_TTL = 6 * 3600
_CACHE_MAX = 256
_CACHE_MAX_BYTES = 800_000


def is_safe_image_name(name: str) -> bool:
    return bool(name and _SAFE_NAME.match(name))


def _cache_get(name: str) -> Optional[Tuple[str, bytes]]:
    hit = _CACHE.get(name)
    if not hit:
        return None
    exp, ctype, body = hit
    if exp < time.time():
        _CACHE.pop(name, None)
        return None
    return ctype, body


def _cache_put(name: str, ctype: str, body: bytes) -> None:
    if len(body) > _CACHE_MAX_BYTES:
        return
    if len(_CACHE) >= _CACHE_MAX:
        # Eviction simple : plus ancien expire
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _CACHE.pop(oldest, None)
    _CACHE[name] = (time.time() + _CACHE_TTL, ctype, body)


def fetch_kfc_image(name: str, size: str = "xs") -> Optional[Tuple[str, bytes]]:
    """Telecharge l'image KFC. Retourne (content_type, bytes) ou None."""
    name = (name or "").strip()
    if not is_safe_image_name(name):
        return None

    cached = _cache_get(name)
    if cached:
        return cached

    sizes = [size] + [s for s in _SIZES if s != size]
    session = requests.Session()
    for sz in sizes:
        for ext in _EXTS:
            url = f"{_BASE}/{sz}/{name}{ext}"
            try:
                r = session.get(url, headers=_HEADERS, timeout=12)
            except requests.RequestException:
                continue
            if r.status_code != 200 or not r.content:
                continue
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip()
            if not ctype.startswith("image/"):
                # Heuristique magic bytes
                raw = r.content
                if raw.startswith(b"\xff\xd8\xff"):
                    ctype = "image/jpeg"
                elif raw.startswith(b"\x89PNG"):
                    ctype = "image/png"
                elif len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
                    ctype = "image/webp"
                else:
                    continue
            _cache_put(name, ctype, r.content)
            return ctype, r.content
    return None


def register_kfc_image_routes(app) -> None:
    """Enregistre ``GET /api/kfc-image/<name>``."""
    from flask import Response, abort, request

    @app.route("/api/kfc-image/<path:name>")
    def api_kfc_image(name: str):
        # strip extension if client passes one
        base = name.strip().split("/")[-1]
        for ext in _EXTS:
            if base.lower().endswith(ext):
                base = base[: -len(ext)]
                break
        size = (request.args.get("s") or "xs").strip().lower()
        if size not in _SIZES:
            size = "xs"
        got = fetch_kfc_image(base, size=size)
        if not got:
            abort(404)
        ctype, body = got
        resp = Response(body, mimetype=ctype)
        resp.headers["Cache-Control"] = "public, max-age=86400"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp
