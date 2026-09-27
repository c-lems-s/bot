-- Moyens de paiement (catalogue) + historique de paiements par user.

CREATE TABLE IF NOT EXISTS moyen_paiement (
    id          BIGSERIAL PRIMARY KEY,
    nom         TEXT NOT NULL,
    lien        TEXT NOT NULL DEFAULT ''
);

COMMENT ON TABLE moyen_paiement IS 'Moyens de paiement affiches dans le portefeuille (nom + lien).';
COMMENT ON COLUMN moyen_paiement.nom IS 'Libelle affiche (ex. Lydia, PayPal).';
COMMENT ON COLUMN moyen_paiement.lien IS 'URL de paiement / recharge.';

CREATE TABLE IF NOT EXISTS user_paiement (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    moyen_paiement_id   BIGINT REFERENCES moyen_paiement (id) ON DELETE SET NULL,
    moyen_nom           TEXT,
    solde               NUMERIC(12, 2) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_paiement_user_created
    ON user_paiement (user_id, created_at DESC);

COMMENT ON TABLE user_paiement IS 'Historique des paiements / recharges par utilisateur.';
COMMENT ON COLUMN user_paiement.solde IS 'Montant du paiement (EUR).';
COMMENT ON COLUMN user_paiement.moyen_nom IS 'Nom du moyen au moment du paiement (snapshot).';
