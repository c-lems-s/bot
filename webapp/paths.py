"""Chemins persistants (uploads) — volume Railway via UPLOADS_ROOT."""

from __future__ import annotations

import os
from pathlib import Path

# Defaut : webapp/uploads (local). Cloud : monter un volume sur /data/uploads
# et poser UPLOADS_ROOT=/data/uploads
_DEFAULT_UPLOADS = Path(__file__).resolve().parent / "uploads"


def uploads_root() -> Path:
    raw = (os.getenv("UPLOADS_ROOT") or "").strip()
    root = Path(raw).expanduser() if raw else _DEFAULT_UPLOADS
    return root.resolve()


def paiements_uploads_dir() -> Path:
    return uploads_root() / "paiements"


def notifications_uploads_dir() -> Path:
    return uploads_root() / "notifications"


def ensure_uploads_dirs() -> dict:
    """Cree les sous-dossiers et verifie l'ecriture. Retourne un diagnostic."""
    root = uploads_root()
    pay = paiements_uploads_dir()
    notif = notifications_uploads_dir()
    errors: list[str] = []
    for d in (root, pay, notif):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"mkdir {d}: {e}")
    probe = root / ".write_probe"
    writable = False
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable = True
    except Exception as e:
        errors.append(f"write {root}: {e}")
        writable = False
    return {
        "root": str(root),
        "paiements": str(pay),
        "notifications": str(notif),
        "writable": writable,
        "errors": errors,
    }
