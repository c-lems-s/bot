-- Solde user : defaut 0 (plus de seed depuis config.balance).

ALTER TABLE users
    ALTER COLUMN balance SET DEFAULT 0;

UPDATE users
SET balance = 0
WHERE balance IS NULL;

ALTER TABLE users
    ALTER COLUMN balance SET NOT NULL;
