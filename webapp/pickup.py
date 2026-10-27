"""Validation nom / prenom / heure de recuperation (checkout)."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, Tuple
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
PICKUP_MAX = time(23, 30)


def now_paris() -> datetime:
    return datetime.now(PARIS)


def parse_pickup_hhmm(raw: str, *, now: datetime | None = None) -> datetime:
    """Parse ``HH:MM`` → datetime Europe/Paris (aujourd'hui).

    Contraintes :
      - >= heure actuelle (a la minute)
      - <= 23:30 le meme jour
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("Heure de recuperation requise")

    # Accepte HH:MM ou HH:MM:SS
    parts = text.split(":")
    if len(parts) < 2:
        raise ValueError("Heure invalide (format HH:MM)")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as e:
        raise ValueError("Heure invalide (format HH:MM)") from e
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Heure invalide")

    ref = now or now_paris()
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=PARIS)
    else:
        ref = ref.astimezone(PARIS)

    candidate = datetime(
        ref.year, ref.month, ref.day, hour, minute, 0, tzinfo=PARIS
    )
    # Arrondi a la minute courante
    floor_now = ref.replace(second=0, microsecond=0)
    max_dt = datetime(
        ref.year, ref.month, ref.day, PICKUP_MAX.hour, PICKUP_MAX.minute, 0, tzinfo=PARIS
    )

    if floor_now > max_dt:
        raise ValueError(
            "Plus de creneau disponible aujourd'hui (max 23h30). "
            "Reessayez demain."
        )
    if candidate < floor_now:
        raise ValueError(
            f"L'heure de recuperation doit etre au moins "
            f"{floor_now.strftime('%H:%M')} (heure actuelle)."
        )
    if candidate > max_dt:
        raise ValueError("L'heure de recuperation ne peut pas depasser 23h30.")
    return candidate


def normalize_pickup_person(nom: str, prenom: str) -> Tuple[str, str]:
    nom_s = " ".join((nom or "").strip().split())
    prenom_s = " ".join((prenom or "").strip().split())
    if not nom_s:
        raise ValueError("Nom requis")
    if not prenom_s:
        raise ValueError("Prenom requis")
    if len(nom_s) > 80:
        raise ValueError("Nom trop long (max 80)")
    if len(prenom_s) > 80:
        raise ValueError("Prenom trop long (max 80)")
    return nom_s, prenom_s


def validate_checkout_pickup(data: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne ``{nom, prenom, pickup_at}`` ou leve ValueError."""
    nom, prenom = normalize_pickup_person(
        str(data.get("nom") or data.get("lastName") or ""),
        str(data.get("prenom") or data.get("firstName") or ""),
    )
    raw_time = (data.get("pickupTime") or data.get("pickup_time") or "").strip()
    if not raw_time:
        raw_iso = data.get("pickupAt") or data.get("pickup_at") or ""
        if raw_iso:
            try:
                dt = datetime.fromisoformat(str(raw_iso).replace("Z", "+00:00"))
            except ValueError as e:
                raise ValueError("pickupAt invalide") from e
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=PARIS)
            else:
                dt = dt.astimezone(PARIS)
            raw_time = dt.strftime("%H:%M")
    pickup_at = parse_pickup_hhmm(str(raw_time))
    return {"nom": nom, "prenom": prenom, "pickup_at": pickup_at}


def pickup_bounds_for_client() -> Dict[str, str]:
    """Bornes UI (HH:MM) pour le jour J a Paris."""
    ref = now_paris().replace(second=0, microsecond=0)
    max_dt = datetime(
        ref.year, ref.month, ref.day, PICKUP_MAX.hour, PICKUP_MAX.minute, 0, tzinfo=PARIS
    )
    available = ref <= max_dt
    # Si on est pile a 23:30, encore OK ; apres → pas de creneau
    min_hhmm = ref.strftime("%H:%M") if available else "23:30"
    return {
        "timezone": "Europe/Paris",
        "min": min_hhmm,
        "max": "23:30",
        "available": available,
        "serverNow": ref.isoformat(),
    }
