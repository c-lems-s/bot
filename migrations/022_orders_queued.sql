-- File d'attente admin : statut QUEUED pour commandes locales a traiter.

ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_status_check;

ALTER TABLE orders
    ADD CONSTRAINT orders_status_check
    CHECK (status IN ('QUEUED', 'SUBMITTED', 'CHECKED_IN', 'FAILED', 'DONE'));

COMMENT ON COLUMN orders.status IS 'QUEUED=file admin; DONE=traitee; legacy SUBMITTED/CHECKED_IN/FAILED.';
