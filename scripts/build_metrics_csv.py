"""
Task 3 – Build Financial Metrics CSV
Reads Screener XLSX files + config/report_sections.yaml and writes
data/financial_metrics.csv with exactly 120 rows (4 companies × 3 FYs × 10 metrics).

Units:
  TCS / INFY         → Screener already in ₹ Crore
  ANGELONE           → Screener in ₹ Crore, PDF in ₹ Million  (1 Cr = 10 M)
  MOTILALOFS         → Screener in ₹ Crore, PDF in ₹ Lakhs    (1 Cr = 100 L)

Cross-checks use pymupdf text extraction against the PDF's consolidated statements.
"""

import csv
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import openpyxl
import pymupdf
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCREENER_DIR = ROOT / "data" / "screener"
CONFIG_PATH  = ROOT / "config" / "report_sections.yaml"
OUT_CSV      = ROOT / "data" / "financial_metrics.csv"

FISCAL_YEAR_MAP = {
    2024: "FY24",
    2025: "FY25",
    2026: "FY26",
}

TICKER_TO_XLSX = {
    "TCS":        "TCS.xlsx",
    "INFY":       "INFY.xlsx",
    "ANGELONE":   "ANGELONE.xlsx",
    "MOTILALOFS": "MOTILALOFS.xlsx",
}

TICKER_TO_COMPANY = {
    "TCS":        "Tata Consultancy Services Limited",
    "INFY":       "Infosys Limited",
    "ANGELONE":   "Angel One Limited",
    "MOTILALOFS": "Motilal Oswal Financial Services Limited",
}

ORDERED_METRICS = [
    "revenue_from_operations",
    "other_income",
    "total_income",
    "operating_profit",
    "finance_costs",
    "profit_before_tax",
    "net_profit",
    "total_debt",
    "total_equity",
    "operating_cash_flow",
]

# ─────────────────────────────────────────────────────────────────────────────
# Screener XLSX reader
# ─────────────────────────────────────────────────────────────────────────────

def read_screener(ticker: str) -> dict[str, dict[str, Decimal]]:
    """
    Returns {fy: {label: Decimal_value}} for FY24/FY25/FY26.
    Labels preserved: Sales, Other Income, Interest, Profit before tax,
                      Net profit, Equity Share Capital, Reserves,
                      Borrowings, Cash from Operating Activity.
    Stops P&L reading at the 'Quarters' header; resumes at BALANCE SHEET / CASH FLOW.
    """
    path = SCREENER_DIR / TICKER_TO_XLSX[ticker]
    wb   = openpyxl.load_workbook(path, data_only=True)
    ws   = wb["Data Sheet"]

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Locate section header rows
    section = None          # 'pnl' | 'bs' | 'cf'
    year_indices: dict[str, int] = {}   # fy -> column index (0-based)
    data: dict[str, dict[str, Decimal]] = {"FY24": {}, "FY25": {}, "FY26": {}}

    for row in rows:
        label = str(row[0]).strip() if row[0] is not None else ""

        # ── Section headers ────────────────────────────────────────────────
        if label == "PROFIT & LOSS":
            section = "pnl"
            continue
        if label == "Quarters":
            section = "quarterly_skip"
            continue
        if label == "BALANCE SHEET":
            section = "bs"
            continue
        if label == "CASH FLOW:":
            section = "cf"
            continue

        # ── Year index row ─────────────────────────────────────────────────
        if label == "Report Date" and section in ("pnl", "bs", "cf"):
            year_indices = {}
            for col_idx, cell in enumerate(row[1:], start=1):
                if cell is None:
                    continue
                try:
                    yr = cell.year
                except AttributeError:
                    continue
                fy = FISCAL_YEAR_MAP.get(yr)
                if fy:
                    year_indices[fy] = col_idx
            continue

        # ── Skip quarterly section ─────────────────────────────────────────
        if section == "quarterly_skip":
            continue

        # ── Data rows ──────────────────────────────────────────────────────
        if section not in ("pnl", "bs", "cf"):
            continue
        if not year_indices:
            continue

        # Collect only the rows we care about
        interesting = {
            "pnl": {"Sales", "Other Income", "Interest",
                    "Profit before tax", "Net profit"},
            "bs":  {"Equity Share Capital", "Reserves", "Borrowings"},
            "cf":  {"Cash from Operating Activity"},
        }
        if label not in interesting.get(section, set()):
            continue

        for fy, col_idx in year_indices.items():
            raw = row[col_idx] if col_idx < len(row) else None
            if raw is None:
                continue
            try:
                val = Decimal(str(raw))
            except InvalidOperation:
                continue
            data[fy][label] = val

    return data


# ─────────────────────────────────────────────────────────────────────────────
# PDF cross-check helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_numbers(text: str) -> list[Decimal]:
    """Return all numeric tokens (allowing commas) from a text block."""
    nums = []
    for tok in re.findall(r"[\d,]+(?:\.\d+)?", text):
        clean = tok.replace(",", "")
        try:
            nums.append(Decimal(clean))
        except InvalidOperation:
            pass
    return nums


def _near(a: Decimal, b: Decimal, tol: Decimal = Decimal("0.5")) -> bool:
    """True if |a-b| <= tol (allowing for rounding in PDF text)."""
    return abs(a - b) <= tol


def crosscheck_pdf(
    report_key: str,
    ticker: str,
    fy: str,
    pdf_path: Path,
    pnl_page: int,       # 1-based
    screener_revenue: Decimal,
    screener_pat: Decimal,
    sector: str,
) -> None:
    """
    Extract text from the PnL page and verify Revenue and PAT are present.
    Angel One PDFs are in ₹ Million → convert Screener Crore to Million for comparison.
    Motilal Oswal PDFs are in ₹ Lakhs → convert Screener Crore to Lakhs.
    TCS / INFY PDFs are in ₹ Crore (direct comparison).
    """
    doc = pymupdf.open(str(pdf_path))
    page_text = doc[pnl_page - 1].get_text("text")
    doc.close()

    nums = _extract_numbers(page_text)

    if ticker == "ANGELONE":
        # Screener: Crore. PDF: Million. 1 Cr = 10 M
        rev_pdf  = screener_revenue * Decimal("10")
        pat_pdf  = screener_pat     * Decimal("10")
        unit_note = "Screener=Crore; PDF=Million → ×10"
    elif ticker == "MOTILALOFS":
        # Screener: Crore. PDF: Lakhs. 1 Cr = 100 L
        rev_pdf  = screener_revenue * Decimal("100")
        pat_pdf  = screener_pat     * Decimal("100")
        unit_note = "Screener=Crore; PDF=Lakhs → ×100"
    else:
        rev_pdf  = screener_revenue
        pat_pdf  = screener_pat
        unit_note = "Screener=Crore; PDF=Crore"

    tol = max(abs(rev_pdf) * Decimal("0.01"), Decimal("2"))  # 1% or 2 units

    rev_found = any(_near(n, rev_pdf, tol) for n in nums)
    pat_found = any(_near(n, pat_pdf, tol) for n in nums)

    status = "✓" if (rev_found and pat_found) else "⚠"
    print(
        f"  XCHECK {report_key} {fy} p{pnl_page}: "
        f"Rev={screener_revenue} ({unit_note}) → PDF≈{rev_pdf:.2f} {'✓' if rev_found else '✗'} | "
        f"PAT={screener_pat} → PDF≈{pat_pdf:.2f} {'✓' if pat_found else '✗'}  {status}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Metric builder
# ─────────────────────────────────────────────────────────────────────────────

def build_metrics(
    ticker: str,
    company: str,
    sector: str,
    fy: str,
    screener: dict[str, Decimal],
    stmt_pages: dict[str, int],
) -> list[dict]:
    """
    Returns a list of 10 metric dicts for one (ticker, fy) combination.
    All values in INR_CRORE using Decimal arithmetic.
    """
    rows = []
    is_broking = (sector == "BROKING_FINTECH")

    def v(label: str) -> Decimal:
        return screener.get(label, Decimal("0"))

    revenue   = v("Sales")
    other_inc = v("Other Income")
    interest  = v("Interest")
    pbt       = v("Profit before tax")
    net_profit= v("Net profit")
    eq_cap    = v("Equity Share Capital")
    reserves  = v("Reserves")
    borrowings= v("Borrowings")
    cfo       = v("Cash from Operating Activity")

    total_income_val  = revenue + other_inc
    total_equity_val  = eq_cap + reserves

    # Operating profit: EBIT for IT_SERVICES; NA for brokers
    if is_broking:
        op_profit_val = "NA"
    else:
        op_profit_val = (pbt + interest - other_inc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    pnl_pg = stmt_pages["pnl"]
    bs_pg  = stmt_pages["bs"]
    cf_pg  = stmt_pages["cf"]

    metric_defs = [
        ("revenue_from_operations", revenue,            "INR_CRORE", "Consolidated_PnL",  pnl_pg),
        ("other_income",            other_inc,          "INR_CRORE", "Consolidated_PnL",  pnl_pg),
        ("total_income",            total_income_val,   "INR_CRORE", "Consolidated_PnL",  pnl_pg),
        ("operating_profit",        op_profit_val,      "INR_CRORE", "Consolidated_PnL",  pnl_pg),
        ("finance_costs",           interest,           "INR_CRORE", "Consolidated_PnL",  pnl_pg),
        ("profit_before_tax",       pbt,                "INR_CRORE", "Consolidated_PnL",  pnl_pg),
        ("net_profit",              net_profit,         "INR_CRORE", "Consolidated_PnL",  pnl_pg),
        ("total_debt",              borrowings,         "INR_CRORE", "Consolidated_BS",   bs_pg),
        ("total_equity",            total_equity_val,   "INR_CRORE", "Consolidated_BS",   bs_pg),
        ("operating_cash_flow",     cfo,                "INR_CRORE", "Consolidated_CF",   cf_pg),
    ]

    for metric, val, unit, stmt_label, page_ref in metric_defs:
        rows.append({
            "ticker":        ticker,
            "company":       company,
            "sector":        sector,
            "fiscal_year":   fy,
            "metric":        metric,
            "value":         str(val),
            "unit":          unit,
            "statement_label": stmt_label,
            "page_ref":      page_ref,
        })

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    all_rows: list[dict] = []
    FYS = ["FY24", "FY25", "FY26"]

    # Group report config by ticker
    by_ticker: dict[str, dict] = {}
    for rkey, rcfg in config["reports"].items():
        ticker = rcfg["ticker"]
        fy     = rcfg["fiscal_year"]
        if ticker not in by_ticker:
            by_ticker[ticker] = {}
        by_ticker[ticker][fy] = rcfg

    for ticker in ["TCS", "INFY", "ANGELONE", "MOTILALOFS"]:
        print(f"\n{'─'*60}")
        print(f"Processing {ticker} ...")
        screener_all = read_screener(ticker)

        for fy in FYS:
            if fy not in by_ticker.get(ticker, {}):
                print(f"  WARNING: no config for {ticker} {fy}")
                continue

            rcfg    = by_ticker[ticker][fy]
            sector  = rcfg["sector"]
            company = TICKER_TO_COMPANY[ticker]
            pdf_path= ROOT / rcfg["pdf_path"]
            stmt    = rcfg["statement_pages"]

            screener = screener_all.get(fy, {})

            # Cross-check
            crosscheck_pdf(
                report_key     = f"{ticker.lower()}_{fy.lower()}",
                ticker         = ticker,
                fy             = fy,
                pdf_path       = pdf_path,
                pnl_page       = stmt["pnl"],
                screener_revenue = screener.get("Sales", Decimal("0")),
                screener_pat     = screener.get("Net profit", Decimal("0")),
                sector         = sector,
            )

            rows = build_metrics(ticker, company, sector, fy, screener, stmt)
            all_rows.extend(rows)

            # Quick sanity print
            rev = screener.get("Sales", Decimal("0"))
            pat = screener.get("Net profit", Decimal("0"))
            print(f"  {fy}: Revenue={rev:>12} | PAT={pat:>10} | rows={len(rows)}")

    # Write CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["ticker","company","sector","fiscal_year","metric",
                  "value","unit","statement_label","page_ref"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n✓ Wrote {len(all_rows)} rows → {OUT_CSV}")

    if len(all_rows) != 120:
        print(f"  ERROR: expected 120 rows, got {len(all_rows)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
