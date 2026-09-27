-- Telegram id de l'admin (droits privilegiés app).

ALTER TABLE config
    ADD COLUMN IF NOT EXISTS admin BIGINT;

COMMENT ON COLUMN config.admin IS 'Telegram id utilisateur admin.';
