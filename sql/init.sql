-- FinSight Phase 2 – Database Initialisation
-- Runs once when the container first starts (docker-entrypoint-initdb.d)

CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────
-- Exact relational store for the 120 validated metric rows
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS financial_metrics (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(16)  NOT NULL,
    company         TEXT         NOT NULL,
    sector          VARCHAR(32)  NOT NULL,
    fiscal_year     VARCHAR(8)   NOT NULL,
    metric          VARCHAR(64)  NOT NULL,
    value           NUMERIC(18, 2),          -- NULL for "NA" rows
    unit            VARCHAR(16)  NOT NULL,
    statement_label VARCHAR(64)  NOT NULL,
    page_ref        INT          NOT NULL,
    UNIQUE (ticker, fiscal_year, metric)
);

CREATE INDEX IF NOT EXISTS idx_metrics_lookup
    ON financial_metrics (ticker, fiscal_year, metric);

-- ─────────────────────────────────────────────────────────────
-- Hybrid chunk store: pgvector HNSW + tsvector GIN
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id           BIGSERIAL PRIMARY KEY,
    chunk_id     VARCHAR(128) UNIQUE NOT NULL,
    ticker       VARCHAR(16)  NOT NULL,
    fiscal_year  VARCHAR(8)   NOT NULL,
    section      VARCHAR(48)  NOT NULL,
    page_number  INT          NOT NULL,
    pdf_file     VARCHAR(64)  NOT NULL,
    content      TEXT         NOT NULL,
    embedding    vector(384),
    tsv          tsvector GENERATED ALWAYS AS
                     (to_tsvector('english', content)) STORED
);

-- Metadata filter index (ticker + fiscal_year + section)
CREATE INDEX IF NOT EXISTS idx_chunks_meta
    ON document_chunks (ticker, fiscal_year, section);

-- Full-text GIN index on the generated tsvector column
CREATE INDEX IF NOT EXISTS idx_chunks_tsv
    ON document_chunks USING GIN (tsv);

-- HNSW cosine index – built after data load so it covers all vectors
-- (created by ingest script after upsert to avoid incremental HNSW cost)
-- CREATE INDEX idx_chunks_embedding ON document_chunks
--     USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);
