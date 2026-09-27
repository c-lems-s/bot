-- Shop ouvert/ferme + prochaine heure d'ouverture (texte libre admin).

ALTER TABLE config
    ADD COLUMN IF NOT EXISTS actif BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE config
    ADD COLUMN IF NOT EXISTS prochaine_heure TEXT;

COMMENT ON COLUMN config.actif IS 'Shop ouvert (true) / ferme (false).';
COMMENT ON COLUMN config.prochaine_heure IS 'Prochaine heure d''ouverture si actif=false (texte libre).';
