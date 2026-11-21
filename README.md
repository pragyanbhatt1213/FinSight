# FinSight

Verifiable financial research engine over NSE/BSE annual reports (TCS, Infosys, Angel One, Motilal Oswal · FY24–FY26) that separates deterministic SQL/Python financial metrics from hybrid `pgvector` narrative retrieval to eliminate LLM math and unit-conversion hallucinations.

## Architecture

- **Structured Layer (`financial_metrics`):** 120 canonical P&L, Balance Sheet, and Cash Flow metrics normalized to ₹ Crore in PostgreSQL for deterministic SQL/Python computation.
- **Unstructured Layer (`document_chunks`):** 4,546 chunks extracted from MD&A, Risk Factors, and financial statements (`config/report_sections.yaml`), indexed in PostgreSQL via `pgvector` HNSW (`BAAI/bge-small-en-v1.5`) and GIN `tsvector` full-text search.
- **Evaluation Benchmark (`data/eval_questions.json`):** 35 stratified questions (25 dev / 10 test) covering numeric lookups, ratios, narrative retrieval, multi-hop comparisons, and out-of-scope refusals.

## Tech Stack

Python 3.12+ · PostgreSQL 16 + `pgvector` · PyMuPDF · `sentence-transformers` (`BAAI/bge-small-en-v1.5`) · Docker Compose · FastAPI & LangGraph *(in progress)*

## Quickstart

```bash
docker compose up -d
python -m venv .venv && .venv\Scripts\activate
pip install psycopg[binary] pgvector pymupdf pyyaml sentence-transformers langchain-text-splitters
python scripts/ingest_phase2.py

## Architecture Overview

```
 ┌───────────────────────── Structured Layer ──────────────────────────┐
 │  Screener XLSX exports + PDF cross-checks                          │
 │       ↓                                                            │
 │  financial_metrics.csv  (120 rows, ₹ Crore, NA for Ind AS Div III  │
 │                          broking/fintech operating margins)         │
 │       ↓                                                            │
 │  PostgreSQL  financial_metrics  table                               │
 │  (deterministic SQL lookups — zero LLM involvement)                │
 └────────────────────────────────────────────────────────────────────┘

 ┌──────────────────────── Unstructured Layer ─────────────────────────┐
 │  config/report_sections.yaml  (page boundaries per report)         │
 │       ↓                                                            │
 │  PyMuPDF extracts MD&A, Risk Factors, financial statement pages    │
 │       ↓                                                            │
 │  RecursiveCharacterTextSplitter (900 chars / 150 overlap)          │
 │       → 4,546 chunks                                               │
 │       ↓                                                            │
 │  BAAI/bge-small-en-v1.5  (384-dim embeddings)                      │
 │       ↓                                                            │
 │  PostgreSQL  document_chunks  table                                 │
 │  ├─ HNSW cosine index   (vector similarity)                        │
 │  └─ GIN index on generated tsvector  (full-text keyword search)    │
 └────────────────────────────────────────────────────────────────────┘

 ┌──────────────────────── Evaluation Benchmark ──────────────────────┐
 │  data/eval_questions.json — 35 stratified questions (25 dev / 10   │
 │  test) across 5 categories:                                        │
 │    numeric_lookup · ratio_computation · text_retrieval             │
 │    multi_hop_compare · unanswerable (out-of-scope refusal)         │
 └────────────────────────────────────────────────────────────────────┘
```