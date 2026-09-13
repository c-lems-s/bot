"""
Applique les migrations SQL numérotées dans migrations/.

Usage :
    python -m db.migrate
"""

from __future__ import annotations

import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

# Racine projet (parent de db/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MIGRATIONS_DIR = os.path.join(_ROOT, "migrations")


def _ensure_path():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)


def _list_migration_files():
    if not os.path.isdir(_MIGRATIONS_DIR):
        return []
    files = []
    for name in os.listdir(_MIGRATIONS_DIR):
        if re.match(r"^\d+_.*\.sql$", name):
            files.append(name)
    return sorted(files)


def migrate() -> int:
    """Applique les migrations manquantes. Retourne le nombre appliqué."""
    _ensure_path()
    from db.connection import get_cursor, init_db

    init_db()
    applied = 0

    with get_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute("SELECT filename FROM schema_migrations")
        done = {row["filename"] for row in cur.fetchall()}

    for name in _list_migration_files():
        if name in done:
            continue
        path = os.path.join(_MIGRATIONS_DIR, name)
        with open(path, "r", encoding="utf-8-sig") as f:
            sql = f.read()
        print(f"[migrate] {name} …")
        with get_cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (name,),
            )
        applied += 1
        print(f"[migrate] {name} OK")

    if applied == 0:
        print("[migrate] Rien à appliquer (à jour).")
    else:
        print(f"[migrate] {applied} migration(s) appliquée(s).")
    return applied


def main():
    try:
        migrate()
    except Exception as e:
        print(f"[-] Migration échouée : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
