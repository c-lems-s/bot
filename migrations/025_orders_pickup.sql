-- Infos retrait client collecteés au checkout.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS pickup_nom TEXT,
    ADD COLUMN IF NOT EXISTS pickup_prenom TEXT,
    ADD COLUMN IF NOT EXISTS pickup_at TIMESTAMPTZ;

COMMENT ON COLUMN orders.pickup_nom IS 'Nom de retrait saisi au checkout';
COMMENT ON COLUMN orders.pickup_prenom IS 'Prenom de retrait saisi au checkout';
COMMENT ON COLUMN orders.pickup_at IS 'Heure de recuperation souhaitee (jour J, Europe/Paris)';
