-- Staff : droits paiement / commandes + journal d'actions
CREATE TABLE IF NOT EXISTS staff (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    can_paiements BOOLEAN NOT NULL DEFAULT FALSE,
    can_commandes BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT staff_has_perm CHECK (can_paiements OR can_commandes)
);

CREATE TABLE IF NOT EXISTS staff_action_log (
    id BIGSERIAL PRIMARY KEY,
    staff_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_telegram_id BIGINT,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staff_action_log_staff
    ON staff_action_log (staff_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_staff_action_log_created
    ON staff_action_log (created_at DESC);
