"""Point d'entree WSGI (gunicorn / Railway).

La preparation DB doit etre faite avant les workers, ex. :
    python -m webapp.boot && gunicorn -c gunicorn.conf.py webapp.wsgi:app
"""

from __future__ import annotations

from webapp.server import app

__all__ = ["app"]
