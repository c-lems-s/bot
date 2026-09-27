-- Statut local apres checkout (plus de SubmitOrder / Checkin KFC).

ALTER TABLE sessions
    DROP CONSTRAINT IF EXISTS sessions_status_check;

ALTER TABLE sessions
    ADD CONSTRAINT sessions_status_check
    CHECK (status IN ('IDLE', 'DRAFT', 'SUBMITTED', 'CHECKED_IN', 'CONFIRMED'));
