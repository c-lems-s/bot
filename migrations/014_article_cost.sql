-- Cout en points fidelite catalogue (limite panier 2500), independant du compte KFC.

ALTER TABLE article
    ADD COLUMN IF NOT EXISTS cost INTEGER;

COMMENT ON COLUMN article.cost IS 'Points fidelite catalogue (plafond panier app).';
