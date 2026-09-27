-- Cycle commande admin : terminer + formulaire / annulation + total EUR.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS terminer BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS annulee BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS annulation_explication TEXT;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS admin_prenom TEXT;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS admin_restaurant TEXT;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS admin_heure_max TEXT;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS admin_lien_preuve TEXT;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS total_eur NUMERIC(12, 2);

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS terminee_at TIMESTAMPTZ;

-- Commandes deja en file (QUEUED) restent en cours
UPDATE orders SET terminer = FALSE WHERE terminer IS NULL;

CREATE INDEX IF NOT EXISTS idx_orders_en_cours
    ON orders (submitted_at ASC)
    WHERE terminer = FALSE;

CREATE INDEX IF NOT EXISTS idx_orders_ma_commande
    ON orders (user_id, terminee_at DESC)
    WHERE terminer = TRUE;

COMMENT ON COLUMN orders.terminer IS 'false=en cours (file admin); true=terminee (faite ou annulee).';
COMMENT ON COLUMN orders.annulee IS 'true si annulee par admin (remboursement).';
COMMENT ON COLUMN orders.total_eur IS 'Montant EUR debite (remboursement si annulation).';
