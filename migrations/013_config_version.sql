-- Numero de version app (affiche en mode ALLOW_DEV_AUTH uniquement).

ALTER TABLE config
    ADD COLUMN IF NOT EXISTS version TEXT NOT NULL DEFAULT '1';

COMMENT ON COLUMN config.version IS 'Version app (UI: v-{version} si ALLOW_DEV_AUTH).';
