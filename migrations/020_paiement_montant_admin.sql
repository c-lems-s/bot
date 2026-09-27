-- Montant declare + refs message admin pour validation paiement.

ALTER TABLE paiement_demande
    ADD COLUMN IF NOT EXISTS montant NUMERIC(12, 2);

ALTER TABLE paiement_demande
    ADD COLUMN IF NOT EXISTS admin_chat_id BIGINT;

ALTER TABLE paiement_demande
    ADD COLUMN IF NOT EXISTS admin_message_id BIGINT;

COMMENT ON COLUMN paiement_demande.montant IS 'Montant EUR declare par le user (credite si accepté).';
COMMENT ON COLUMN paiement_demande.admin_chat_id IS 'Chat Telegram admin (notif review).';
COMMENT ON COLUMN paiement_demande.admin_message_id IS 'Message Telegram admin avec boutons.';
