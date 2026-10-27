"""
Connexion PostgreSQL (pool thread-safe).

Config via DATABASE_URL ou DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD.
La config shop (réduction, admin, actif…) est dans la table Postgres `config`.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional

from dotenv import load_dotenv

load_dotenv()

# Evite UnicodeDecodeError sur messages d'erreur libpq (Windows / locale FR).
os.environ.setdefault("PGCLIENTENCODING", "UTF8")

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "psycopg2-binary est requis. Installez : pip install psycopg2-binary"
    ) from e

_connection_pool: Optional[pool.ThreadedConnectionPool] = None


def _normalize_database_url(url: str) -> str:
    """Adapte DATABASE_URL Railway / Heroku pour psycopg2.

    - ``postgres://`` → ``postgresql://``
    - ajoute ``sslmode=require`` en cloud si absent (Railway)
    """
    url = (url or "").strip()
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    # sslmode deja present ?
    if "sslmode=" in url.lower():
        return url

    try:
        from webapp.env import is_cloud

        cloud = is_cloud()
    except Exception:
        cloud = bool(
            os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME")
        )

    force = (os.getenv("PGSSLMODE") or "").strip().lower()
    if force:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}sslmode={force}"

    if cloud:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}sslmode=require"
    return url


def _dsn_kwargs() -> dict:
    url = _normalize_database_url(os.getenv("DATABASE_URL") or "")
    if url:
        return {"dsn": url}
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "dbname": os.getenv("DB_NAME", "kfc_perso"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "root"),
    }


def get_pool() -> pool.ThreadedConnectionPool:
    """Retourne ou crée le pool de connexions."""
    global _connection_pool
    if _connection_pool is None:
        kwargs = _dsn_kwargs()
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=8,
            **kwargs,
        )
    return _connection_pool


def init_db() -> None:
    """Initialise le pool (à appeler au démarrage)."""
    get_pool()


def close_pool() -> None:
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None


@contextmanager
def get_connection() -> Generator:
    conn = get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        get_pool().putconn(conn)


@contextmanager
def get_cursor(dict_cursor: bool = True) -> Generator:
    """Curseur dict par défaut (RealDictCursor)."""
    with get_connection() as conn:
        factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=factory)
        try:
            yield cur
        finally:
            cur.close()
