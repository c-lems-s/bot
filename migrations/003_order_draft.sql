-- Singleton draft cart (mono-compte) for restart recovery.

CREATE TABLE IF NOT EXISTS order_draft (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    status          TEXT NOT NULL DEFAULT 'IDLE',
    store_id        TEXT,
    store_name      TEXT,
    store_city      TEXT,
    basket_id       TEXT,
    cart_json       JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_order_json JSONB,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO order_draft (id, status)
VALUES (1, 'IDLE')
ON CONFLICT (id) DO NOTHING;
