-- Pourcentage du prix catalogue facture / affiche (ex. 30 = client paie 30%).
-- Prix barre = catalogue ; prix client = price * reduction / 100.

ALTER TABLE config
    ADD COLUMN IF NOT EXISTS reduction NUMERIC(6, 2) NOT NULL DEFAULT 100
        CHECK (reduction >= 0 AND reduction <= 100);

COMMENT ON COLUMN config.reduction IS
    'Pourcentage du prix catalogue applique (30 = 30% du prix).';
