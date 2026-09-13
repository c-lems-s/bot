-- Attach orders to Telegram users / sessions.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS session_id BIGINT REFERENCES sessions(id);

CREATE INDEX IF NOT EXISTS idx_orders_user_submitted
    ON orders (user_id, submitted_at DESC);
