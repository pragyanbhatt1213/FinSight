"""
Task 1 – PDF Discovery Script
Scans all 12 PDFs in data/raw_reports/ and writes data/pdf_discovery_report.json
plus a console summary.
"""

import json
import re
import sys
from pathlib import Path

import pymupdf  # pymupdf >= 1.23 uses `import pymupdf`

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw_reports"
OUT_JSON = ROOT / "data" / "pdf_discovery_report.json"

# ------------------------------------------------------------------
# Pattern catalogue
# ------------------------------------------------------------------
SECTION_PATTERNS = {
    "consolidated_bs": [
        r"consolidated\s+balance\s+sheet",
    ],
    "consolidated_pnl": [
        r"consolidated\s+statement\s+of\s+profit\s+(and|&)\s+loss",
        r"consolidated\s+profit\s+(and|&)\s+loss",
        r"consolidated\s+statement\s+of\s+income",
    ],
    "consolidated_cf": [
        r"consolidated\s+(statement\s+of\s+)?cash\s+flow",
    ],
    "business_overview": [
        r"business\s+overview",
        r"company\s+overview",
        r"about\s+us",
        r"integrated\s+report",
        r"about\s+the\s+company",
        r"corporate\s+overview",
    ],
    "mda": [
        r"management('s)?\s+(discussion\s+(and|&)\s+analysis|review)",
        r"md\s*&\s*a",
        r"management\s+discussion",
    ],
    "risk_factors": [
        r"risk\s+management",
        r"key\s+risks",
        r"risk\s+factors",
        r"enterprise\s+risk\s+management",
        r"principal\s+risks",
    ],
}

COMPILED = {
    sec: [re.compile(p, re.IGNORECASE) for p in pats]
    for sec, pats in SECTION_PATTERNS.items()
}

FIN_SECTIONS = {"consolidated_bs", "consolidated_pnl", "consolidated_cf"}


def scan_pdf(pdf_path: Path) -> dict:
    doc = pymupdf.open(str(pdf_path))
    total_pages = len(doc)

    # --- TOC bookmarks ---
    toc_raw = doc.get_toc()  # [[level, title, page], ...]
    toc = []
    for level, title, page in toc_raw:
        if 1 <= level <= 3:
            toc.append({"level": level, "title": title, "page_1based": page})

    # --- Page-by-page heading scan ---
    section_hits: dict[str, list] = {sec: [] for sec in SECTION_PATTERNS}

    for page_idx in range(total_pages):
        page = doc[page_idx]
        # Top 900 chars of the page text
        text = page.get_text("text")[:900]
        text_lower = text.lower()
        page_num = page_idx + 1  # 1-based

        for sec, patterns in COMPILED.items():
            for pat in patterns:
                if pat.search(text_lower):
                    # Collect a 5-line snippet for financial statement pages
                    snippet = None
                    if sec in FIN_SECTIONS:
                        lines = text.strip().splitlines()
                        snippet = "\n".join(lines[:5])
                    section_hits[sec].append(
                        {"page_1based": page_num, "snippet": snippet}
                    )
                    break  # one hit per section per page is enough

    doc.close()

    return {
        "file": pdf_path.name,
        "total_pages": total_pages,
        "toc": toc,
        "section_hits": section_hits,
    }


def main():
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"ERROR: No PDFs found in {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    report = {}

    for pdf_path in pdfs:
        key = pdf_path.stem  # e.g. "tcs_fy24"
        print(f"\n{'='*60}")
        print(f"Scanning: {pdf_path.name}")
        result = scan_pdf(pdf_path)
        report[key] = result

        print(f"  Total pages : {result['total_pages']}")
        print(f"  TOC entries : {len(result['toc'])}")

        for sec, hits in result["section_hits"].items():
            if hits:
                pages = [h["page_1based"] for h in hits]
                print(f"  [{sec}] pages: {pages}")

        # Print snippets for financial statement candidate pages
        for sec in FIN_SECTIONS:
            hits = result["section_hits"][sec]
            if hits:
                print(f"\n  --- {sec} snippets ---")
                for h in hits[:3]:  # show up to 3 candidates
                    print(f"  Page {h['page_1based']}:")
                    if h["snippet"]:
                        for line in h["snippet"].splitlines():
                            print(f"    {line}")

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n\nDiscovery report written → {OUT_JSON}")


if __name__ == "__main__":
    main()
