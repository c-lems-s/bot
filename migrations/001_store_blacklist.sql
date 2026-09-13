-- Blacklist of ineligible loyalty stores.

CREATE TABLE IF NOT EXISTS store_blacklist (
    store_id       TEXT PRIMARY KEY,
    name           TEXT,
    city           TEXT,
    matched_items  INTEGER,
    reason         TEXT NOT NULL DEFAULT 'loyalty_match',
    blacklisted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
