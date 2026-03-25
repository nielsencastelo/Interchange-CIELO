-- ============================================================
-- Interchange AI — Schema PostgreSQL v2.0
-- ============================================================
-- Criação: psql -U postgres -d interchange_ai -f sql/001_schema.sql
-- Ou via Docker: docker compose exec db psql -U postgres -d interchange_ai -f /sql/001_schema.sql
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- Tabela principal: regras de intercâmbio
-- ============================================================
CREATE TABLE IF NOT EXISTS interchange_rule_app (
    id               SERIAL          PRIMARY KEY,
    network          VARCHAR(32)     NOT NULL,
    region           VARCHAR(16)     NOT NULL DEFAULT 'BR',
    rule_type        VARCHAR(64)     NOT NULL,
    audience         VARCHAR(16),
    card_family      VARCHAR(32),
    product          VARCHAR(128),
    merchant_group   VARCHAR(256),
    channel          VARCHAR(64),
    installment_band VARCHAR(32),
    rate_pct         NUMERIC(8,4),
    fixed_fee_amount NUMERIC(10,4),
    currency         VARCHAR(8)      DEFAULT 'BRL',
    cap_amount       NUMERIC(10,4),
    floor_amount     NUMERIC(10,4),
    effective_from   DATE,
    effective_to     DATE,
    evidence_text    TEXT            NOT NULL DEFAULT '',
    page_number      INTEGER,
    confidence_score NUMERIC(4,3)    NOT NULL DEFAULT 0.500
                         CHECK (confidence_score >= 0 AND confidence_score <= 1),
    metadata_json    JSONB           DEFAULT '{}',
    version_tag      VARCHAR(32),
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_rule_network      ON interchange_rule_app (network);
CREATE INDEX IF NOT EXISTS idx_rule_region       ON interchange_rule_app (region);
CREATE INDEX IF NOT EXISTS idx_rule_type         ON interchange_rule_app (rule_type);
CREATE INDEX IF NOT EXISTS idx_rule_card_family  ON interchange_rule_app (card_family);
CREATE INDEX IF NOT EXISTS idx_rule_product      ON interchange_rule_app (product);
CREATE INDEX IF NOT EXISTS idx_rule_audience     ON interchange_rule_app (audience);
CREATE INDEX IF NOT EXISTS idx_rule_channel      ON interchange_rule_app (channel);
CREATE INDEX IF NOT EXISTS idx_rule_confidence   ON interchange_rule_app (confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_rule_version      ON interchange_rule_app (version_tag);
CREATE INDEX IF NOT EXISTS idx_rule_network_fam  ON interchange_rule_app (network, card_family, product);
CREATE INDEX IF NOT EXISTS idx_rule_evidence_trgm
    ON interchange_rule_app USING GIN (evidence_text gin_trgm_ops);

-- ============================================================
-- Log de extrações
-- ============================================================
CREATE TABLE IF NOT EXISTS extraction_log (
    id              SERIAL          PRIMARY KEY,
    source_path     TEXT            NOT NULL,
    network         VARCHAR(32)     NOT NULL,
    region          VARCHAR(16)     NOT NULL DEFAULT 'BR',
    total_rules     INTEGER         NOT NULL DEFAULT 0,
    high_confidence INTEGER         NOT NULL DEFAULT 0,
    low_confidence  INTEGER         NOT NULL DEFAULT 0,
    warnings        TEXT            DEFAULT '',
    status          VARCHAR(32)     NOT NULL DEFAULT 'success',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_log_network    ON extraction_log (network);
CREATE INDEX IF NOT EXISTS idx_log_status     ON extraction_log (status);
CREATE INDEX IF NOT EXISTS idx_log_created    ON extraction_log (created_at DESC);

-- ============================================================
-- View: comparativo de taxas base por produto
-- ============================================================
CREATE OR REPLACE VIEW vw_base_rates_comparison AS
SELECT
    network, card_family, product,
    AVG(rate_pct)         AS avg_rate_pct,
    MIN(rate_pct)         AS min_rate_pct,
    MAX(rate_pct)         AS max_rate_pct,
    COUNT(*)              AS rule_count,
    AVG(confidence_score) AS avg_confidence
FROM interchange_rule_app
WHERE rule_type = 'base_rate' AND rate_pct IS NOT NULL
GROUP BY network, card_family, product
ORDER BY network, card_family, avg_rate_pct DESC;

-- ============================================================
-- View: estatísticas por bandeira
-- ============================================================
CREATE OR REPLACE VIEW vw_network_stats AS
SELECT
    network,
    COUNT(*)                                                         AS total_rules,
    COUNT(*) FILTER (WHERE rule_type = 'base_rate')                  AS base_rates,
    COUNT(*) FILTER (WHERE rule_type LIKE '%adjustment%')            AS adjustments,
    COUNT(*) FILTER (WHERE rule_type = 'fixed_fee')                  AS fixed_fees,
    COUNT(*) FILTER (WHERE rule_type IN ('cap','floor','regulatory_cap')) AS limits,
    AVG(rate_pct) FILTER (WHERE rule_type = 'base_rate')             AS avg_base_rate,
    MIN(rate_pct) FILTER (WHERE rule_type = 'base_rate')             AS min_base_rate,
    MAX(rate_pct) FILTER (WHERE rule_type = 'base_rate')             AS max_base_rate,
    AVG(confidence_score)                                            AS avg_confidence
FROM interchange_rule_app
GROUP BY network
ORDER BY network;

-- ============================================================
-- View: aderência regulatória BCB (débito e pré-pago)
-- ============================================================
CREATE OR REPLACE VIEW vw_bcb_compliance AS
SELECT
    r.network, r.card_family, r.product, r.merchant_group,
    r.rate_pct          AS actual_rate,
    lim.rate_pct        AS bcb_limit,
    lim.cap_amount      AS bcb_cap,
    CASE
        WHEN lim.rate_pct IS NOT NULL AND r.rate_pct > lim.rate_pct THEN 'ACIMA_DO_LIMITE'
        WHEN lim.cap_amount IS NOT NULL                               THEN 'SUJEITO_A_CAP'
        ELSE 'CONFORME'
    END AS bcb_status
FROM interchange_rule_app r
LEFT JOIN interchange_rule_app lim
    ON lim.network = 'BCB_Limite'
   AND lim.card_family = r.card_family
   AND r.rule_type = 'base_rate'
WHERE r.network != 'BCB_Limite'
  AND r.card_family IN ('debit', 'prepaid')
  AND r.rule_type = 'base_rate';

COMMENT ON TABLE interchange_rule_app IS
    'Regras de intercâmbio — Visa, Mastercard, AmericanExpress, Elo, Hipercard, BCB_Limite';
COMMENT ON COLUMN interchange_rule_app.confidence_score IS
    'Score de confiança da extração [0.0-1.0]: >=0.80 alta, 0.50-0.79 média, <0.50 revisão humana';
COMMENT ON COLUMN interchange_rule_app.version_tag IS
    'Tag de versionamento: ex. "2024-Q1", "2025-Q2"';

SELECT 'Schema v2.0 criado com sucesso! Bandeiras: Visa, Mastercard, Amex, Elo, Hipercard, BCB' AS status;
