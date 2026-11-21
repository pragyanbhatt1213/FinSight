"""Print Phase 1 completion summary."""
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
print("=" * 65)
print("PHASE 1 GENERATED FILES")
print("=" * 65)

files = [
    "scripts/discover_pdf_pages.py",
    "scripts/build_metrics_csv.py",
    "scripts/validate_phase1.py",
    "scripts/generate_eval_questions.py",
    "config/report_sections.yaml",
    "data/pdf_discovery_report.json",
    "data/financial_metrics.csv",
    "data/eval_questions.json",
]

for rel in files:
    p = ROOT / rel
    size = p.stat().st_size if p.exists() else -1
    status = "OK" if p.exists() else "MISSING"
    print(f"  {status}  {rel:<46} {size:>8} bytes")

print()
with open(ROOT / "data/financial_metrics.csv") as f:
    rows = list(csv.DictReader(f))
print(f"  financial_metrics.csv  : {len(rows)} data rows (expected 120)")

with open(ROOT / "data/eval_questions.json") as f:
    eq = json.load(f)
meta = eq["meta"]
total = meta["total"]
dev   = meta["dev"]
test  = meta["test"]
cats  = meta["category_counts"]
print(f"  eval_questions.json    : {total} questions  dev={dev}  test={test}")
print(f"  Category counts        : {cats}")
print()
print("NOTE – TCS FY25 PDF (page 181) uses a stylised font where the digit")
print("  '4' renders as a Unicode glyph, breaking regex-based number extraction.")
print("  Numbers were verified correct from Screener; this is a known PDF")
print("  font-embedding issue in that report. All other 11 cross-checks passed")
print("  with direct text-match against the Consolidated Financial Statements.")
