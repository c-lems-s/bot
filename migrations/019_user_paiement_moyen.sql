-- Alignement user_paiement : colonne « moyen » (libelle), plus de moyen_nom.

ALTER TABLE user_paiement
    RENAME COLUMN moyen_nom TO moyen;

COMMENT ON COLUMN user_paiement.moyen IS 'Libelle du moyen de paiement (snapshot).';
