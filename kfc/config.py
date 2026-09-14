"""
Configuration KFC globale — lue depuis la table Postgres `config` (id=1).

Plus de fichier config.json au runtime.
Pour importer un ancien config.json une fois :
    python -m db.seed_config
"""

from __future__ import annotations

from typing import Any, Dict

_CACHE: Dict[str, Any] | None = None


def clear_cache() -> None:
    global _CACHE
    _CACHE = None


def load_config(*, force: bool = False) -> Dict[str, Any]:
    """Charge la config depuis Postgres. Raises RuntimeError si absente / DB KO."""
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE

    try:
        from db.repositories import config as config_repo
    except Exception as e:
        raise RuntimeError(
            "Impossible d'importer le repository config (Postgres requis)."
        ) from e

    try:
        row = config_repo.get()
    except Exception as e:
        raise RuntimeError(
            f"Lecture table config impossible : {e}\n"
            "Verifiez .env puis : python -m db.ensure_db"
        ) from e

    if row is None:
        raise RuntimeError(
            "Aucune ligne dans la table config.\n"
            "Lancez : python -m db.migrate  puis  python -m db.seed_config"
        )

    try:
        reduction = float(row.get("reduction") if row.get("reduction") is not None else 100)
    except (TypeError, ValueError):
        reduction = 100.0

    _CACHE = {
        "account_id": row.get("account_id") or "",
        "authorization": row.get("authorization") or "",
        "cookies": row.get("cookies") or {},
        "recaptcha_token": row.get("recaptcha_token") or "",
        "enable_analytics": bool(row.get("enable_analytics", False)),
        "balance": float(row.get("balance") if row.get("balance") is not None else 0.98),
        "currency": row.get("currency") or "EUR",
        "reduction": max(0.0, min(100.0, reduction)),
    }
    return _CACHE


def get_account_id() -> str:
    return load_config().get("account_id", "") or ""


def get_authorization() -> str:
    return load_config().get("authorization", "") or ""


def get_cookies() -> Dict[str, str]:
    raw = load_config().get("cookies", {}) or {}
    return {str(k): str(v) for k, v in raw.items()}


def get_recaptcha_token() -> str:
    """Jeton reCAPTCHA manuel (fallback si le bypass auto echoue)."""
    return load_config().get("recaptcha_token", "") or ""


def analytics_enabled() -> bool:
    return bool(load_config().get("enable_analytics", False))


def get_balance() -> float:
    """Solde de depart pour nouveaux users (seed), lu depuis table config."""
    try:
        return float(load_config().get("balance", 0.98))
    except (RuntimeError, ValueError, TypeError):
        return 0.98


def get_currency() -> str:
    try:
        return load_config().get("currency", "EUR") or "EUR"
    except RuntimeError:
        return "EUR"


def get_reduction() -> float:
    """Pourcentage du prix catalogue applique (30 = 30% du prix)."""
    try:
        return float(load_config().get("reduction", 100))
    except (RuntimeError, ValueError, TypeError):
        return 100.0


def apply_reduction(price: float, reduction: float | None = None) -> float:
    """Prix client = catalogue * reduction / 100."""
    if reduction is None:
        reduction = get_reduction()
    try:
        p = float(price)
        r = float(reduction)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, p) * max(0.0, min(100.0, r)) / 100.0, 2)
