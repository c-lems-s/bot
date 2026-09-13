-- Config KFC globale (1 seule ligne). Remplace config.json.
-- auth_token = header Authorization (Bearer …) ; authorization est reserve SQL.

CREATE TABLE IF NOT EXISTS config (
    id               SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    account_id       TEXT NOT NULL DEFAULT '',
    auth_token       TEXT NOT NULL DEFAULT '',
    cookies          JSONB NOT NULL DEFAULT '{}'::jsonb,
    recaptcha_token  TEXT NOT NULL DEFAULT '',
    enable_analytics BOOLEAN NOT NULL DEFAULT FALSE,
    balance          NUMERIC(12, 2) NOT NULL DEFAULT 0.98,
    currency         TEXT NOT NULL DEFAULT 'EUR',
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO config (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE config IS 'Secrets / parametres compte KFC partage (ex-config.json).';
COMMENT ON COLUMN config.auth_token IS 'Header Authorization Bearer (ex-authorization JSON).';
