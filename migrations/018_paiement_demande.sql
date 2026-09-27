-- Demandes de recharge solde + preuves (captures ecran).

CREATE TABLE IF NOT EXISTS paiement_demande (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    moyen_paiement_id   BIGINT REFERENCES moyen_paiement (id) ON DELETE SET NULL,
    moyen_nom           TEXT NOT NULL DEFAULT '',
    lien                TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT', 'PENDING', 'ACCEPTED', 'REJECTED')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalized_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_paiement_demande_user
    ON paiement_demande (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS paiement_preuve (
    id              BIGSERIAL PRIMARY KEY,
    demande_id      BIGINT NOT NULL REFERENCES paiement_demande (id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    mime            TEXT,
    stored_name     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paiement_preuve_demande
    ON paiement_preuve (demande_id);

COMMENT ON TABLE paiement_demande IS 'Demande de recharge solde (brouillon puis attente admin).';
COMMENT ON TABLE paiement_preuve IS 'Captures ecran / preuves jointes a une demande.';
