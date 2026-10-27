-- Menu fidélité partagé entre workers gunicorn (évite « Article introuvable »).

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS menu_json JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN sessions.menu_json IS
    'Cache menu KFC (items par id) pour la session DRAFT — partagé multi-workers';
