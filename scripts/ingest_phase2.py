"""
Phase 2 Ingestion Script
========================
1. Upserts 120 validated rows into financial_metrics.
2. Extracts text from every section in config/report_sections.yaml
   (business_overview, mda, risk_factors) plus the three financial-
   statement pages (pnl, bs, cf) for each of the 12 reports.
3. Splits into ~900-char overlapping chunks, embeds with
   BAAI/bge-small-en-v1.5 (384-dim), upserts into document_chunks.
4. Builds an HNSW cosine index on document_chunks.embedding once
   all vectors are loaded.
"""

import csv
import os
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg
import pymupdf
import yaml
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

ROOT      = Path(__file__).resolve().parent.parent
CSV_PATH  = ROOT / "data" / "financial_metrics.csv"
YAML_PATH = ROOT / "config" / "report_sections.yaml"

DB_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://finsight:finsight_dev@localhost:5432/finsight",
)
EMBED_MODEL   = "BAAI/bge-small-en-v1.5"
CHUNK_SIZE    = 900
CHUNK_OVERLAP = 150
EMBED_BATCH   = 64
MIN_CHUNK_LEN = 80   # skip pages with < 80 chars of extractable text


# ─────────────────────────────────────────────────────────────────────────────
# Step A – financial_metrics
# ─────────────────────────────────────────────────────────────────────────────

UPSERT_METRIC = """
    INSERT INTO financial_metrics
        (ticker, company, sector, fiscal_year, metric,
         value, unit, statement_label, page_ref)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (ticker, fiscal_year, metric) DO UPDATE SET
        value           = EXCLUDED.value,
        unit            = EXCLUDED.unit,
        statement_label = EXCLUDED.statement_label,
        page_ref        = EXCLUDED.page_ref;
"""


def ingest_metrics(conn: psycopg.Connection) -> int:
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with conn.cursor() as cur:
        for r in rows:
            raw_val = r["value"].strip()
            try:
                val = Decimal(raw_val)
            except InvalidOperation:
                val = None   # "NA" rows → SQL NULL

            cur.execute(
                UPSERT_METRIC,
                (
                    r["ticker"],
                    r["company"],
                    r["sector"],
                    r["fiscal_year"],
                    r["metric"],
                    val,
                    r["unit"],
                    r["statement_label"],
                    int(r["page_ref"]),
                ),
            )
    conn.commit()
    print(f"  ✓ financial_metrics: upserted {len(rows)} rows")
    return len(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Step B – text extraction + chunking
# ─────────────────────────────────────────────────────────────────────────────

def build_chunks(cfg: dict) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size    = CHUNK_SIZE,
        chunk_overlap = CHUNK_OVERLAP,
        separators    = ["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks: list[dict] = []
    report_stats: list[tuple] = []

    for rkey, rcfg in cfg["reports"].items():
        ticker   = rcfg["ticker"]
        fy       = rcfg["fiscal_year"]
        pdf_path = ROOT / rcfg["pdf_path"]
        pdf_name = pdf_path.name

        doc        = pymupdf.open(str(pdf_path))
        total_pgs  = len(doc)
        rkey_count = 0

        # ── Narrative sections ────────────────────────────────────────────
        for sec_name, bounds in rcfg["sections"].items():
            sp = bounds["start_page"]
            ep = bounds["end_page"]
            for pg in range(sp, ep + 1):
                if not (1 <= pg <= total_pgs):
                    continue
                raw = doc[pg - 1].get_text("text").strip()
                if len(raw) < MIN_CHUNK_LEN:
                    continue
                prefix = f"[{ticker} | {fy} | {sec_name} | Page {pg}]\n"
                for idx, chunk in enumerate(splitter.split_text(raw)):
                    all_chunks.append({
                        "chunk_id":   f"{ticker}_{fy}_{sec_name}_p{pg:04d}_c{idx:03d}",
                        "ticker":     ticker,
                        "fiscal_year": fy,
                        "section":    sec_name,
                        "page_number": pg,
                        "pdf_file":   pdf_name,
                        "content":    prefix + chunk,
                    })
                    rkey_count += 1

        # ── Financial statement pages ─────────────────────────────────────
        for stmt_type, pg in rcfg["statement_pages"].items():
            if not (1 <= pg <= total_pgs):
                continue
            raw = doc[pg - 1].get_text("text").strip()
            if len(raw) < MIN_CHUNK_LEN:
                continue
            prefix = f"[{ticker} | {fy} | {stmt_type.upper()} | Page {pg}]\n"
            sec_label = f"statement_{stmt_type}"
            for idx, chunk in enumerate(splitter.split_text(raw)):
                all_chunks.append({
                    "chunk_id":    f"{ticker}_{fy}_{sec_label}_p{pg:04d}_c{idx:03d}",
                    "ticker":      ticker,
                    "fiscal_year": fy,
                    "section":     sec_label,
                    "page_number": pg,
                    "pdf_file":    pdf_name,
                    "content":     prefix + chunk,
                })
                rkey_count += 1

        doc.close()
        report_stats.append((rkey, rkey_count))

    # Print per-report summary
    for rkey, cnt in report_stats:
        print(f"    {rkey:<26} → {cnt:>4} chunks")

    return all_chunks


# ─────────────────────────────────────────────────────────────────────────────
# Step C – embed + upsert
# ─────────────────────────────────────────────────────────────────────────────

UPSERT_CHUNK = """
    INSERT INTO document_chunks
        (chunk_id, ticker, fiscal_year, section,
         page_number, pdf_file, content, embedding)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (chunk_id) DO UPDATE SET
        content   = EXCLUDED.content,
        embedding = EXCLUDED.embedding;
"""


def ingest_chunks(
    conn: psycopg.Connection,
    chunks: list[dict],
    model: SentenceTransformer,
) -> int:
    texts = [c["content"] for c in chunks]

    print(f"\n  Embedding {len(texts)} chunks in batches of {EMBED_BATCH} ...")
    t0 = time.time()
    embeddings = model.encode(
        texts,
        batch_size         = EMBED_BATCH,
        show_progress_bar  = True,
        normalize_embeddings = True,
        convert_to_numpy   = True,
    )
    elapsed = time.time() - t0
    print(f"  Embedding done in {elapsed:.1f}s")

    print("  Upserting chunks into document_chunks ...")
    with conn.cursor() as cur:
        for c, emb in zip(chunks, embeddings):
            cur.execute(
                UPSERT_CHUNK,
                (
                    c["chunk_id"],
                    c["ticker"],
                    c["fiscal_year"],
                    c["section"],
                    c["page_number"],
                    c["pdf_file"],
                    c["content"],
                    emb.tolist(),
                ),
            )
    conn.commit()
    return len(chunks)


# ─────────────────────────────────────────────────────────────────────────────
# Step D – HNSW index
# ─────────────────────────────────────────────────────────────────────────────

def build_hnsw_index(conn: psycopg.Connection) -> None:
    """
    Build HNSW cosine index after all vectors are loaded.
    Uses m=16, ef_construction=64 (good balance of recall vs build time).
    PostgreSQL requires SET maintenance_work_mem before CREATE INDEX for HNSW.
    """
    print("\n  Building HNSW cosine index on document_chunks.embedding ...")
    with conn.cursor() as cur:
        cur.execute("SET maintenance_work_mem = '512MB';")
        # Drop any stale index from a previous run
        cur.execute(
            "DROP INDEX IF EXISTS idx_chunks_embedding;"
        )
        cur.execute(
            """
            CREATE INDEX idx_chunks_embedding
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """
        )
    conn.commit()
    print("  HNSW index created.")


# ─────────────────────────────────────────────────────────────────────────────
# Step E – verify
# ─────────────────────────────────────────────────────────────────────────────

def verify(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM financial_metrics;")
        n_metrics = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM document_chunks;")
        n_chunks = cur.fetchone()[0]

        cur.execute(
            "SELECT ticker, fiscal_year, COUNT(*) AS n "
            "FROM document_chunks "
            "GROUP BY ticker, fiscal_year "
            "ORDER BY ticker, fiscal_year;"
        )
        breakdown = cur.fetchall()

        # Quick semantic test: nearest neighbours for a sample query
        sample_query = "What is TCS revenue from operations FY2024?"
        register_vector(conn)

    print("\n" + "═" * 60)
    print("  PHASE 2 VERIFICATION")
    print("═" * 60)
    print(f"  financial_metrics rows : {n_metrics}")
    print(f"  document_chunks total  : {n_chunks}")
    print()
    print(f"  {'Ticker':<14} {'FY':<6} {'Chunks':>8}")
    print(f"  {'─'*14} {'─'*6} {'─'*8}")
    for ticker, fy, cnt in breakdown:
        print(f"  {ticker:<14} {fy:<6} {cnt:>8}")

    # Verify HNSW index exists
    with conn.cursor() as cur:
        cur.execute(
            "SELECT indexname, indexdef "
            "FROM pg_indexes "
            "WHERE tablename = 'document_chunks' "
            "AND indexname = 'idx_chunks_embedding';"
        )
        idx = cur.fetchone()
    if idx:
        print(f"\n  HNSW index : {idx[0]} ✓")
    else:
        print("\n  HNSW index : NOT FOUND ✗")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))

    print(f"\nConnecting to {DB_DSN.split('@')[-1]} ...")
    with psycopg.connect(DB_DSN) as conn:
        register_vector(conn)

        # ── A. Metrics ───────────────────────────────────────────────────
        print("\n[A] Ingesting financial_metrics ...")
        ingest_metrics(conn)

        # ── B. Build chunks ──────────────────────────────────────────────
        print("\n[B] Extracting + chunking text from 12 PDFs ...")
        chunks = build_chunks(cfg)
        print(f"\n  Total chunks built: {len(chunks)}")

        # ── C. Load model + embed + upsert ───────────────────────────────
        print(f"\n[C] Loading embedding model: {EMBED_MODEL}")
        model = SentenceTransformer(EMBED_MODEL)
        print(f"  Embedding dimension: {model.get_sentence_embedding_dimension()}")
        n_chunks = ingest_chunks(conn, chunks, model)
        print(f"  ✓ Upserted {n_chunks} chunks into document_chunks")

        # ── D. HNSW index ────────────────────────────────────────────────
        print("\n[D] Building HNSW index ...")
        build_hnsw_index(conn)

        # ── E. Verify ────────────────────────────────────────────────────
        verify(conn)

    print("\n  Phase 2 ingestion complete ✓")


if __name__ == "__main__":
    main()
