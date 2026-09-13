-- Order history (snapshot at KFC submit).

CREATE TABLE IF NOT EXISTS orders (
    id                SERIAL PRIMARY KEY,
    order_uuid        TEXT UNIQUE,
    order_number      TEXT,
    confirmation_url  TEXT,
    store_id          TEXT,
    store_name        TEXT,
    store_city        TEXT,
    status            TEXT NOT NULL
        CHECK (status IN ('SUBMITTED', 'CHECKED_IN', 'FAILED')),
    total_points      INTEGER NOT NULL DEFAULT 0 CHECK (total_points >= 0),
    account_id        TEXT,
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checked_in_at     TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_submitted_at
    ON orders (submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_orders_order_uuid
    ON orders (order_uuid)
    WHERE order_uuid IS NOT NULL;

CREATE TABLE IF NOT EXISTS order_items (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    loyalty_id   TEXT,
    name         TEXT,
    cost         INTEGER NOT NULL DEFAULT 0 CHECK (cost >= 0),
    quantity     INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    modgrps      JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id
    ON order_items (order_id);
