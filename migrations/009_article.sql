-- Catalogue articles (edition manuelle).
-- kfc_item_id = id universel menu KFC (ex. loyalty-xxxx).
-- label = categorie affichee dans la mini-app.
-- Absents de cette table = "Bientot disponible" (non selectionnables).

CREATE TABLE IF NOT EXISTS article (
    id              BIGSERIAL PRIMARY KEY,
    kfc_item_id     TEXT NOT NULL UNIQUE,
    name            TEXT,
    label           TEXT NOT NULL,
    price           NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_article_label ON article (label);
CREATE INDEX IF NOT EXISTS idx_article_kfc_item_id ON article (kfc_item_id);

COMMENT ON TABLE article IS 'Prix EUR + label UI; rempli/modifie a la main.';
COMMENT ON COLUMN article.kfc_item_id IS 'Id menu KFC universel (loyalty-xxx).';
COMMENT ON COLUMN article.label IS 'Categorie boutique (ex. Desserts, Buckets).';
COMMENT ON COLUMN article.price IS 'Prix client en EUR.';
