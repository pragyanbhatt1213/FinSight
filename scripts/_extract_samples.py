"""Helper: extract text samples from narrative sections for question grounding."""
import pymupdf, yaml, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "config/report_sections.yaml") as f:
    cfg = yaml.safe_load(f)

samples = {}
for rkey, rcfg in cfg["reports"].items():
    pdf_path = ROOT / rcfg["pdf_path"]
    doc = pymupdf.open(str(pdf_path))
    result = {}
    for sec in ["mda", "risk_factors"]:
        sp = rcfg["sections"][sec]["start_page"]
        ep = min(sp + 3, rcfg["sections"][sec]["end_page"])
        pages_text = {}
        for pg in range(sp, ep + 1):
            if pg <= len(doc):
                pages_text[pg] = doc[pg - 1].get_text("text")[:800]
        result[sec] = {"start_pg": sp, "pages": pages_text}
    samples[rkey] = result
    doc.close()

out = ROOT / "data" / "narrative_samples.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(samples, f, indent=2, ensure_ascii=False)
print(f"Written {out}")

# Print summaries
for rkey, v in samples.items():
    print(f"\n=== {rkey} ===")
    for sec, d in v.items():
        for pg, txt in d["pages"].items():
            clean = txt.replace("\n", " ").strip()[:250]
            print(f"  [{sec} p{pg}] {clean}")
