"""
Task 4 – Phase 1 Validation Script
Validates financial_metrics.csv and config/report_sections.yaml,
then prints a clean summary table.
"""

import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf
import yaml

ROOT      = Path(__file__).resolve().parent.parent
CSV_PATH  = ROOT / "data" / "financial_metrics.csv"
YAML_PATH = ROOT / "config" / "report_sections.yaml"

EXPECTED_TICKERS   = {"TCS", "INFY", "ANGELONE", "MOTILALOFS"}
EXPECTED_FYS       = {"FY24", "FY25", "FY26"}
EXPECTED_METRICS   = {
    "revenue_from_operations", "other_income", "total_income",
    "operating_profit", "finance_costs", "profit_before_tax",
    "net_profit", "total_debt", "total_equity", "operating_cash_flow",
}
BROKING_TICKERS = {"ANGELONE", "MOTILALOFS"}

DISPLAY_METRICS = [
    ("revenue_from_operations", "Revenue"),
    ("profit_before_tax",       "PBT"),
    ("net_profit",              "PAT"),
    ("total_debt",              "Debt"),
    ("total_equity",            "Equity"),
    ("operating_cash_flow",     "CFO"),
]

# ────────────────────────────────────────────────────���────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def fmt_crore(v: str) -> str:
    """Format a Decimal-string crore value for display."""
    if v == "NA":
        return "NA"
    try:
        d = Decimal(v)
        return f"{d:>12,.2f}"
    except InvalidOperation:
        return v[:12]


def check_pdf_page(pdf_path: Path, page_1based: int) -> bool:
    """Return True if the page exists and has non-empty extractable text."""
    try:
        doc = pymupdf.open(str(pdf_path))
        total = len(doc)
        if not (1 <= page_1based <= total):
            doc.close()
            return False
        text = doc[page_1based - 1].get_text("text").strip()
        doc.close()
        return len(text) > 0
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Check 1 – CSV structure
# ─────────────────────────────────────────────────────────────────────────────

def validate_csv(rows: list[dict]) -> list[str]:
    errors: list[str] = []

    # Row count
    if len(rows) != 120:
        errors.append(f"Row count: expected 120, got {len(rows)}")

    # Duplicate keys
    seen = {}
    for r in rows:
        key = (r["ticker"], r["fiscal_year"], r["metric"])
        if key in seen:
            errors.append(f"Duplicate key: {key}")
        seen[key] = True

    # Zero / negative page_ref
    for r in rows:
        try:
            pg = int(r["page_ref"])
        except (ValueError, TypeError):
            errors.append(f"Non-integer page_ref in {r}")
            continue
        if pg <= 0:
            errors.append(f"page_ref <= 0 in {r['ticker']} {r['fiscal_year']} {r['metric']}: {pg}")

    # Valid Decimal for non-NA rows; NA iff broking operating_profit
    for r in rows:
        v = r["value"]
        m = r["metric"]
        t = r["ticker"]
        is_broking = t in BROKING_TICKERS

        if m == "operating_profit":
            if is_broking and v != "NA":
                errors.append(f"{t} {r['fiscal_year']} operating_profit should be NA (broking), got {v}")
            if not is_broking and v == "NA":
                errors.append(f"{t} {r['fiscal_year']} operating_profit is NA but sector=IT_SERVICES")
            if v != "NA":
                try:
                    Decimal(v)
                except InvalidOperation:
                    errors.append(f"Cannot parse Decimal: {t} {r['fiscal_year']} {m} = {v}")
        else:
            try:
                Decimal(v)
            except InvalidOperation:
                errors.append(f"Cannot parse Decimal: {t} {r['fiscal_year']} {m} = {v}")

    # Coverage: every (ticker, fy, metric) combination
    for ticker in EXPECTED_TICKERS:
        for fy in EXPECTED_FYS:
            for metric in EXPECTED_METRICS:
                if (ticker, fy, metric) not in seen:
                    errors.append(f"Missing: ({ticker}, {fy}, {metric})")

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Check 2 – Page references
# ─────────────────────────────────────────────────────────────────────────────

def validate_pages(rows: list[dict], config: dict) -> list[str]:
    errors: list[str] = []

    # Build ticker+fy → pdf_path map from YAML
    pdf_map: dict[tuple, Path] = {}
    total_pages_map: dict[tuple, int] = {}
    for rkey, rcfg in config["reports"].items():
        ticker = rcfg["ticker"]
        fy     = rcfg["fiscal_year"]
        pdf_p  = ROOT / rcfg["pdf_path"]
        pdf_map[(ticker, fy)]         = pdf_p
        total_pages_map[(ticker, fy)] = rcfg["total_pages"]

    # CSV page_refs
    checked_csv: set[tuple] = set()
    for r in rows:
        key = (r["ticker"], r["fiscal_year"], r["metric"])
        pair = (r["ticker"], r["fiscal_year"])
        pdf_path = pdf_map.get(pair)
        if pdf_path is None:
            errors.append(f"No PDF path for {pair}")
            continue
        pg = int(r["page_ref"])
        total = total_pages_map.get(pair, 9999)
        if not (1 <= pg <= total):
            errors.append(f"page_ref {pg} out of range [1,{total}] for {key}")
        elif pair not in checked_csv:
            # Check text extraction once per (ticker, fy)
            if not check_pdf_page(pdf_path, pg):
                errors.append(f"Empty/invalid text at page {pg} of {pdf_path.name}")
            checked_csv.add(pair)

    # YAML section ranges
    for rkey, rcfg in config["reports"].items():
        ticker   = rcfg["ticker"]
        fy       = rcfg["fiscal_year"]
        pdf_path = ROOT / rcfg["pdf_path"]
        total    = rcfg["total_pages"]

        # Statement pages
        for stype, pg in rcfg["statement_pages"].items():
            if not (1 <= pg <= total):
                errors.append(f"{rkey} statement_pages.{stype}={pg} out of range [1,{total}]")
            else:
                if not check_pdf_page(pdf_path, pg):
                    errors.append(f"{rkey} statement_pages.{stype} p{pg}: empty text")

        # Section ranges
        for sec, sec_cfg in rcfg["sections"].items():
            sp = sec_cfg["start_page"]
            ep = sec_cfg["end_page"]
            if sp < 1 or ep > total or sp > ep:
                errors.append(f"{rkey} sections.{sec} [{sp},{ep}] invalid (total={total})")

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Summary table
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(rows: list[dict]) -> None:
    # Build lookup {(ticker, fy, metric): value}
    lkp: dict[tuple, str] = {}
    for r in rows:
        lkp[(r["ticker"], r["fiscal_year"], r["metric"])] = r["value"]

    tickers = ["TCS", "INFY", "ANGELONE", "MOTILALOFS"]
    fys     = ["FY24", "FY25", "FY26"]

    print("\n" + "═"*110)
    print("  FINANCIAL METRICS SUMMARY  (₹ Crore, Screener consolidated data)")
    print("═"*110)

    # Header
    hdr = f"{'Ticker':<14} {'FY':<6}"
    for _, short in DISPLAY_METRICS:
        hdr += f" {short:>13}"
    print(hdr)
    print("─"*110)

    for ticker in tickers:
        for fy in fys:
            line = f"{ticker:<14} {fy:<6}"
            for metric_key, _ in DISPLAY_METRICS:
                val = lkp.get((ticker, fy, metric_key), "?")
                line += f" {fmt_crore(val):>13}"
            print(line)
        print("─"*110)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # Load data
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with open(YAML_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    all_errors: list[str] = []

    print("\n" + "="*60)
    print("CHECK 1 – CSV structure & values")
    print("="*60)
    csv_errors = validate_csv(rows)
    if csv_errors:
        for e in csv_errors:
            print(f"  FAIL  {e}")
        all_errors.extend(csv_errors)
    else:
        print(f"  PASS  120 rows, no duplicates, no bad page_refs, all Decimals valid")

    print("\n" + "="*60)
    print("CHECK 2 – Page references vs PDFs")
    print("="*60)
    page_errors = validate_pages(rows, config)
    if page_errors:
        for e in page_errors:
            print(f"  FAIL  {e}")
        all_errors.extend(page_errors)
    else:
        print(f"  PASS  All statement pages and section ranges valid + non-empty text")

    # Summary table
    print_summary(rows)

    print("\n" + "="*60)
    if all_errors:
        print(f"VALIDATION RESULT: FAIL  ({len(all_errors)} errors)")
        sys.exit(1)
    else:
        print("VALIDATION RESULT: PASS ✓")


if __name__ == "__main__":
    main()
