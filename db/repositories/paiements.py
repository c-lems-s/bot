"""Repository PostgreSQL — moyens de paiement + historique user."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from db.connection import get_cursor


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def list_moyens() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, nom, lien
            FROM moyen_paiement
            ORDER BY id ASC
            """
        )
        return [
            {
                "id": int(r["id"]),
                "nom": r.get("nom") or "",
                "lien": r.get("lien") or "",
            }
            for r in cur.fetchall()
        ]


def get_moyen(moyen_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, nom, lien
            FROM moyen_paiement
            WHERE id = %s
            """,
            (int(moyen_id),),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": int(r["id"]),
            "nom": r.get("nom") or "",
            "lien": r.get("lien") or "",
        }


def list_user_paiements(user_id: int, *, limit: int = 50) -> List[Dict[str, Any]]:
    """Historique : paiements acceptes + demandes en attente (PENDING)."""
    limit = max(1, min(200, int(limit)))
    with get_cursor() as cur:
        cur.execute(
            """
            (
                SELECT
                    p.id,
                    p.solde,
                    p.created_at AS ts,
                    COALESCE(p.moyen, m.nom, '') AS moyen,
                    'ACCEPTED'::text AS status
                FROM user_paiement p
                LEFT JOIN moyen_paiement m ON m.id = p.moyen_paiement_id
                WHERE p.user_id = %s
            )
            UNION ALL
            (
                SELECT
                    d.id,
                    d.montant AS solde,
                    COALESCE(d.finalized_at, d.created_at) AS ts,
                    COALESCE(d.moyen_nom, '') AS moyen,
                    d.status::text AS status
                FROM paiement_demande d
                WHERE d.user_id = %s
                  AND d.status IN ('PENDING', 'REJECTED')
            )
            ORDER BY ts DESC
            LIMIT %s
            """,
            (int(user_id), int(user_id), limit),
        )
        rows = []
        for r in cur.fetchall():
            solde_raw = r.get("solde")
            rows.append(
                {
                    "id": int(r["id"]),
                    "solde": _f(solde_raw),
                    "date": r["ts"].isoformat() if r.get("ts") else None,
                    "moyen": r.get("moyen") or "",
                    "status": r.get("status") or "ACCEPTED",
                }
            )
        return rows


def create_demande(user_id: int, moyen_id: int) -> Optional[Dict[str, Any]]:
    moyen = get_moyen(moyen_id)
    if not moyen:
        return None
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO paiement_demande (
                user_id, moyen_paiement_id, moyen_nom, lien, status, created_at
            )
            VALUES (%s, %s, %s, %s, 'DRAFT', NOW())
            RETURNING *
            """,
            (
                int(user_id),
                int(moyen["id"]),
                moyen["nom"],
                moyen["lien"],
            ),
        )
        return _demande_row(cur.fetchone(), preuve_count=0)


def get_demande(demande_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT d.*, (
                SELECT COUNT(*)::int FROM paiement_preuve p WHERE p.demande_id = d.id
            ) AS preuve_count
            FROM paiement_demande d
            WHERE d.id = %s AND d.user_id = %s
            """,
            (int(demande_id), int(user_id)),
        )
        row = cur.fetchone()
        return _demande_row(row) if row else None


def get_demande_by_id(demande_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT d.*, (
                SELECT COUNT(*)::int FROM paiement_preuve p WHERE p.demande_id = d.id
            ) AS preuve_count
            FROM paiement_demande d
            WHERE d.id = %s
            """,
            (int(demande_id),),
        )
        row = cur.fetchone()
        return _demande_row(row) if row else None


def set_montant(demande_id: int, user_id: int, montant: float) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE paiement_demande
            SET montant = %s
            WHERE id = %s AND user_id = %s AND status = 'DRAFT'
            RETURNING *
            """,
            (float(montant), int(demande_id), int(user_id)),
        )
        row = cur.fetchone()
        return _demande_row(row) if row else None


def add_preuve(
    demande_id: int,
    user_id: int,
    *,
    filename: str,
    mime: Optional[str],
    stored_name: str,
) -> Optional[Dict[str, Any]]:
    dem = get_demande(demande_id, user_id)
    if not dem or dem["status"] != "DRAFT":
        return None
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO paiement_preuve (demande_id, filename, mime, stored_name, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id, demande_id, filename, mime, stored_name, created_at
            """,
            (
                int(demande_id),
                (filename or "preuve")[:255],
                (mime or "")[:120] or None,
                stored_name,
            ),
        )
        r = cur.fetchone()
        return {
            "id": int(r["id"]),
            "filename": r.get("filename") or "",
            "mime": r.get("mime"),
            "storedName": r.get("stored_name") or "",
        }


def list_preuves(demande_id: int, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    if user_id is not None:
        dem = get_demande(demande_id, user_id)
        if not dem:
            return []
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, filename, mime, stored_name, created_at
            FROM paiement_preuve
            WHERE demande_id = %s
            ORDER BY id ASC
            """,
            (int(demande_id),),
        )
        return [
            {
                "id": int(r["id"]),
                "filename": r.get("filename") or "",
                "mime": r.get("mime"),
                "storedName": r.get("stored_name") or "",
                "date": r["created_at"].isoformat() if r.get("created_at") else None,
            }
            for r in cur.fetchall()
        ]


def finalize_demande(
    demande_id: int,
    user_id: int,
    *,
    montant: float,
) -> Optional[Dict[str, Any]]:
    dem = get_demande(demande_id, user_id)
    if not dem:
        return None
    if dem["status"] != "DRAFT":
        return dem
    if int(dem.get("preuveCount") or 0) < 1:
        return None
    if montant is None or float(montant) <= 0:
        return None
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE paiement_demande
            SET status = 'PENDING',
                montant = %s,
                finalized_at = NOW()
            WHERE id = %s AND user_id = %s AND status = 'DRAFT'
            RETURNING *
            """,
            (float(montant), int(demande_id), int(user_id)),
        )
        row = cur.fetchone()
        if not row:
            return get_demande(demande_id, user_id)
        return _demande_row(row, preuve_count=dem.get("preuveCount") or 0)


def set_admin_message(demande_id: int, chat_id: int, message_id: int) -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE paiement_demande
            SET admin_chat_id = %s, admin_message_id = %s
            WHERE id = %s
            """,
            (int(chat_id), int(message_id), int(demande_id)),
        )


def accept_demande(demande_id: int) -> Optional[Dict[str, Any]]:
    """Passe PENDING -> ACCEPTED. Retourne la demande ou None."""
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE paiement_demande
            SET status = 'ACCEPTED'
            WHERE id = %s AND status = 'PENDING'
            RETURNING *
            """,
            (int(demande_id),),
        )
        row = cur.fetchone()
        return _demande_row(row) if row else None


def reject_demande(demande_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE paiement_demande
            SET status = 'REJECTED'
            WHERE id = %s AND status = 'PENDING'
            RETURNING *
            """,
            (int(demande_id),),
        )
        row = cur.fetchone()
        return _demande_row(row) if row else None


def _demande_row(row: Any, preuve_count: Optional[int] = None) -> Dict[str, Any]:
    count = preuve_count
    if count is None:
        count = row.get("preuve_count")
    try:
        count = int(count or 0)
    except (TypeError, ValueError):
        count = 0
    montant = _f(row.get("montant"))
    return {
        "id": int(row["id"]),
        "userId": int(row["user_id"]),
        "moyenId": int(row["moyen_paiement_id"]) if row.get("moyen_paiement_id") else None,
        "moyenNom": row.get("moyen_nom") or "",
        "lien": row.get("lien") or "",
        "montant": montant,
        "status": row.get("status") or "DRAFT",
        "preuveCount": count,
        "adminChatId": int(row["admin_chat_id"]) if row.get("admin_chat_id") else None,
        "adminMessageId": int(row["admin_message_id"]) if row.get("admin_message_id") else None,
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
        "finalizedAt": row["finalized_at"].isoformat() if row.get("finalized_at") else None,
    }


def add_user_paiement(
    user_id: int,
    *,
    solde: float,
    moyen_paiement_id: Optional[int] = None,
    moyen: Optional[str] = None,
) -> Dict[str, Any]:
    """Enregistre un paiement accepte (historique)."""
    nom = (moyen or "").strip() or None
    mid = int(moyen_paiement_id) if moyen_paiement_id is not None else None

    with get_cursor() as cur:
        if mid is not None and not nom:
            cur.execute(
                "SELECT nom FROM moyen_paiement WHERE id = %s",
                (mid,),
            )
            row = cur.fetchone()
            if row:
                nom = row.get("nom") or None

        cur.execute(
            """
            INSERT INTO user_paiement (
                user_id, moyen_paiement_id, moyen, solde, created_at
            )
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id, user_id, moyen_paiement_id, moyen, solde, created_at
            """,
            (int(user_id), mid, nom, float(solde)),
        )
        r = cur.fetchone()
        return {
            "id": int(r["id"]),
            "solde": _f(r.get("solde")) or 0.0,
            "date": r["created_at"].isoformat() if r.get("created_at") else None,
            "moyen": r.get("moyen") or "",
            "status": "ACCEPTED",
        }
