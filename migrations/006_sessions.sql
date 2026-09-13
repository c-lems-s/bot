-- Per-user order sessions (replaces in-memory STATE).

CREATE TABLE IF NOT EXISTS sessions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'IDLE'
        CHECK (status IN ('IDLE', 'DRAFT', 'SUBMITTED', 'CHECKED_IN')),
    store_id        TEXT,
    store_name      TEXT,
    store_city      TEXT,
    basket_id       TEXT,
    cart_json       JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_order_json JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_status
    ON sessions (user_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_user_draft
    ON sessions (user_id)
    WHERE status = 'DRAFT';
