-- Solde EUR par utilisateur Telegram (independant du portefeuille points KFC).
-- NULL = pas encore initialise ; rempli au prochain upsert (seed config.json).

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS balance NUMERIC(12, 2);
