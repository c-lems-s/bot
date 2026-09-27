"""
Configuration shop — lue depuis la table Postgres `config` (id=1).

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
        "balance": float(row.get("balance") if row.get("balance") is not None else 0.98),
        "currency": row.get("currency") or "EUR",
        "reduction": max(0.0, min(100.0, reduction)),
        "version": str(row.get("version") or "1"),
        "admin": row.get("admin"),
        "actif": bool(row.get("actif", True)) if row.get("actif") is not None else True,
        "prochaine_heure": row.get("prochaine_heure"),
    }
    return _CACHE


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


def get_version() -> str:
    """Numero de version (table config)."""
    try:
        return str(load_config().get("version") or "1")
    except RuntimeError:
        return "1"


def get_admin() -> int | None:
    """Telegram id admin (table config.admin), ou None."""
    try:
        raw = load_config().get("admin")
    except RuntimeError:
        return None
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def is_admin(telegram_id) -> bool:
    """True si telegram_id correspond a config.admin."""
    admin = get_admin()
    if admin is None:
        return False
    try:
        return int(telegram_id) == admin
    except (TypeError, ValueError):
        return False


def is_shop_actif() -> bool:
    try:
        return bool(load_config().get("actif", True))
    except RuntimeError:
        return True


def get_prochaine_heure() -> str | None:
    try:
        raw = load_config().get("prochaine_heure")
    except RuntimeError:
        return None
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def shop_inactive_message() -> str:
    """Message affiche aux users quand le shop est inactif."""
    heure = get_prochaine_heure()
    affichage = heure if heure else "aucune date fourni par l'admin"
    return (
        "Le shop est inactif pour le moment.\n\n"
        "Vous devez attendre qu'il soit a nouveau actif pour commander. "
        "La disponibilite depend des moments de la journee.\n\n"
        "La prochaine heure d'ouverture sera :\n"
        f"{affichage}"
    )


def set_shop_actif(actif: bool) -> Dict[str, Any]:
    from db.repositories import config as config_repo

    row = config_repo.set_actif(bool(actif))
    clear_cache()
    return row


def set_prochaine_heure(heure: str | None) -> Dict[str, Any]:
    from db.repositories import config as config_repo

    row = config_repo.set_prochaine_heure(heure)
    clear_cache()
    return row
