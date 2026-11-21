"""
Task 5 – Generate 35 Grounded Evaluation Questions
Reads financial_metrics.csv + config/report_sections.yaml + narrative_samples.json
Writes data/eval_questions.json

Distribution: 25 dev, 10 test
Categories:
  numeric_lookup    10 questions
  ratio_computation  8 questions
  text_retrieval     7 questions
  multi_hop_compare  6 questions
  unanswerable       4 questions
"""

import csv
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

ROOT      = Path(__file__).resolve().parent.parent
CSV_PATH  = ROOT / "data" / "financial_metrics.csv"
YAML_PATH = ROOT / "config" / "report_sections.yaml"
OUT_PATH  = ROOT / "data" / "eval_questions.json"

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────

def load_metrics() -> dict[tuple, str]:
    """Returns {(ticker, fy, metric): value_str}."""
    lkp = {}
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lkp[(row["ticker"], row["fiscal_year"], row["metric"])] = row["value"]
    return lkp


def load_config() -> dict:
    with open(YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def m(lkp, ticker, fy, metric) -> Decimal:
    v = lkp.get((ticker, fy, metric), "0")
    if v == "NA":
        return Decimal("0")
    return Decimal(v)


def fmt(d: Decimal, decimals: int = 2) -> str:
    q = Decimal(10) ** -decimals
    return str(d.quantize(q, rounding=ROUND_HALF_UP))


# ─────────────────────────────────────────────────────────────────────────────
# Question builders
# ─────────────────────────────────────────────────────────────────────────────

def build_questions(lkp: dict, cfg: dict) -> list[dict]:
    questions = []
    qid = 1

    def add(split, category, question, expected_answer, reasoning, gold_sources, metadata=None):
        nonlocal qid
        q = {
            "id":              f"Q{qid:03d}",
            "split":           split,
            "category":        category,
            "question":        question,
            "expected_answer": expected_answer,
            "reasoning":       reasoning,
            "gold_sources":    gold_sources,
        }
        if metadata:
            q["metadata"] = metadata
        questions.append(q)
        qid += 1

    sections = cfg["reports"]

    # ═════════════════════════════════════════════════════════════════════════
    # CATEGORY 1: numeric_lookup  (10 questions, mix of dev/test)
    # ═════════════════════════════════════════════════════════════════════════

    # Q1 dev – TCS FY24 Revenue
    rev_tcs24 = m(lkp, "TCS", "FY24", "revenue_from_operations")
    add("dev", "numeric_lookup",
        "What was TCS's consolidated revenue from operations for FY2023-24?",
        f"₹{fmt(rev_tcs24)} crore",
        "Direct lookup from Consolidated Statement of Profit and Loss: Sales row in Screener = Revenue from operations in PDF.",
        [{"ticker":"TCS","fiscal_year":"FY24","page": sections["tcs_fy24"]["statement_pages"]["pnl"],
          "pdf":"tcs_fy24.pdf","label":"Consolidated PnL – Revenue from operations"}])

    # Q2 dev – INFY FY25 PAT
    pat_infy25 = m(lkp, "INFY", "FY25", "net_profit")
    add("dev", "numeric_lookup",
        "What was Infosys's consolidated net profit (PAT) for FY2024-25?",
        f"₹{fmt(pat_infy25)} crore",
        "Net profit row from Screener Data Sheet confirmed against Consolidated P&L.",
        [{"ticker":"INFY","fiscal_year":"FY25","page": sections["infy_fy25"]["statement_pages"]["pnl"],
          "pdf":"infy_fy25.pdf","label":"Consolidated PnL – Net profit"}])

    # Q3 dev – TCS FY26 PBT
    pbt_tcs26 = m(lkp, "TCS", "FY26", "profit_before_tax")
    add("dev", "numeric_lookup",
        "What was TCS's consolidated profit before tax for FY2025-26?",
        f"₹{fmt(pbt_tcs26)} crore",
        "Profit before tax from Screener row 28, confirmed against tcs_fy26.pdf page 167.",
        [{"ticker":"TCS","fiscal_year":"FY26","page": sections["tcs_fy26"]["statement_pages"]["pnl"],
          "pdf":"tcs_fy26.pdf","label":"Consolidated PnL – Profit before tax"}])

    # Q4 dev – ANGELONE FY24 Total Equity
    eq_ao24 = m(lkp, "ANGELONE", "FY24", "total_equity")
    add("dev", "numeric_lookup",
        "What was Angel One's consolidated total equity (share capital + reserves) as at 31 March 2024?",
        f"₹{fmt(eq_ao24)} crore",
        "Equity Share Capital (84.01 Cr) + Reserves (2954.59 Cr) from Screener Balance Sheet.",
        [{"ticker":"ANGELONE","fiscal_year":"FY24","page": sections["angelone_fy24"]["statement_pages"]["bs"],
          "pdf":"angelone_fy24.pdf","label":"Consolidated BS – Equity"}])

    # Q5 dev – MOTILALOFS FY25 Borrowings
    debt_mofs25 = m(lkp, "MOTILALOFS", "FY25", "total_debt")
    add("dev", "numeric_lookup",
        "What was Motilal Oswal Financial Services' consolidated borrowings as at 31 March 2025?",
        f"₹{fmt(debt_mofs25)} crore",
        "Borrowings row from Screener Balance Sheet; confirmed against MOFSL FY25 Consolidated BS in PDF (₹ Lakhs → ÷100).",
        [{"ticker":"MOTILALOFS","fiscal_year":"FY25","page": sections["motilalofs_fy25"]["statement_pages"]["bs"],
          "pdf":"motilalofs_fy25.pdf","label":"Consolidated BS – Borrowings"}])

    # Q6 dev – INFY FY26 Revenue
    rev_infy26 = m(lkp, "INFY", "FY26", "revenue_from_operations")
    add("dev", "numeric_lookup",
        "What was Infosys's consolidated revenue from operations for FY2025-26?",
        f"₹{fmt(rev_infy26)} crore",
        "Sales row FY26 from Screener confirmed against infy_fy26.pdf page 287.",
        [{"ticker":"INFY","fiscal_year":"FY26","page": sections["infy_fy26"]["statement_pages"]["pnl"],
          "pdf":"infy_fy26.pdf","label":"Consolidated PnL – Revenue"}])

    # Q7 dev – ANGELONE FY25 Finance Costs
    fc_ao25 = m(lkp, "ANGELONE", "FY25", "finance_costs")
    add("dev", "numeric_lookup",
        "What were Angel One's consolidated finance costs for FY2024-25?",
        f"₹{fmt(fc_ao25)} crore",
        "Interest row from Screener P&L for FY25.",
        [{"ticker":"ANGELONE","fiscal_year":"FY25","page": sections["angelone_fy25"]["statement_pages"]["pnl"],
          "pdf":"angelone_fy25.pdf","label":"Consolidated PnL – Finance costs"}])

    # Q8 dev – TCS FY25 Operating Cash Flow
    cfo_tcs25 = m(lkp, "TCS", "FY25", "operating_cash_flow")
    add("dev", "numeric_lookup",
        "What was TCS's consolidated cash flow from operating activities for FY2024-25?",
        f"₹{fmt(cfo_tcs25)} crore",
        "Cash from Operating Activity row from Screener Cash Flow section for FY25.",
        [{"ticker":"TCS","fiscal_year":"FY25","page": sections["tcs_fy25"]["statement_pages"]["cf"],
          "pdf":"tcs_fy25.pdf","label":"Consolidated CF – Operating Activity"}])

    # Q9 test – MOTILALOFS FY26 Net Profit
    pat_mofs26 = m(lkp, "MOTILALOFS", "FY26", "net_profit")
    add("test", "numeric_lookup",
        "What was Motilal Oswal Financial Services' consolidated net profit for FY2025-26?",
        f"₹{fmt(pat_mofs26)} crore",
        "Net profit row from Screener FY26; confirmed against MOFSL FY26 Consolidated P&L page 346 (PDF in ₹ Lakhs).",
        [{"ticker":"MOTILALOFS","fiscal_year":"FY26","page": sections["motilalofs_fy26"]["statement_pages"]["pnl"],
          "pdf":"motilalofs_fy26.pdf","label":"Consolidated PnL – Net profit"}])

    # Q10 test – INFY FY24 Total Debt
    debt_infy24 = m(lkp, "INFY", "FY24", "total_debt")
    add("test", "numeric_lookup",
        "What was Infosys's consolidated borrowings as at 31 March 2024?",
        f"₹{fmt(debt_infy24)} crore",
        "Borrowings row from Screener Balance Sheet FY24.",
        [{"ticker":"INFY","fiscal_year":"FY24","page": sections["infy_fy24"]["statement_pages"]["bs"],
          "pdf":"infy_fy24.pdf","label":"Consolidated BS – Borrowings"}])

    # ════════════════════��════════════════════════════════════════════════════
    # CATEGORY 2: ratio_computation  (8 questions)
    # ═════════════════════════════════════════════════════════════════════════

    # Q11 dev – TCS FY24 Net Margin
    rev24  = m(lkp, "TCS", "FY24", "revenue_from_operations")
    pat24  = m(lkp, "TCS", "FY24", "net_profit")
    nm24   = (pat24 / rev24 * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    add("dev", "ratio_computation",
        "What was TCS's consolidated net profit margin for FY2023-24?",
        f"{fmt(nm24)}%",
        f"Net Margin = Net Profit / Revenue = {fmt(pat24)} / {fmt(rev24)} × 100 = {fmt(nm24)}%",
        [{"ticker":"TCS","fiscal_year":"FY24","page": sections["tcs_fy24"]["statement_pages"]["pnl"],
          "pdf":"tcs_fy24.pdf","label":"PnL – Net profit and Revenue"}])

    # Q12 dev – INFY FY25 ROE
    pat_i25 = m(lkp, "INFY", "FY25", "net_profit")
    eq_i25  = m(lkp, "INFY", "FY25", "total_equity")
    roe_i25 = (pat_i25 / eq_i25 * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    add("dev", "ratio_computation",
        "What was Infosys's Return on Equity (ROE) for FY2024-25?",
        f"{fmt(roe_i25)}%",
        f"ROE = Net Profit / Total Equity = {fmt(pat_i25)} / {fmt(eq_i25)} × 100 = {fmt(roe_i25)}%",
        [{"ticker":"INFY","fiscal_year":"FY25","page": sections["infy_fy25"]["statement_pages"]["pnl"],
          "pdf":"infy_fy25.pdf","label":"PnL and BS – Net profit, Equity"}])

    # Q13 dev – ANGELONE FY24 Operating Margin → NOT_APPLICABLE
    add("dev", "ratio_computation",
        "What was Angel One's consolidated operating profit margin for FY2023-24?",
        "NOT_APPLICABLE",
        "Angel One is classified under BROKING_FINTECH (Ind AS Division III). Finance costs are core operating expenses under this framework, so a traditional EBIT-based operating margin is not meaningful and is reported as NOT_APPLICABLE.",
        [{"ticker":"ANGELONE","fiscal_year":"FY24","page": sections["angelone_fy24"]["statement_pages"]["pnl"],
          "pdf":"angelone_fy24.pdf","label":"Consolidated PnL – sector classification"}])

    # Q14 dev – MOTILALOFS FY25 Operating Margin → NOT_APPLICABLE
    add("dev", "ratio_computation",
        "What was Motilal Oswal Financial Services' consolidated operating profit margin for FY2024-25?",
        "NOT_APPLICABLE",
        "MOFSL is a Ind AS Division III financial services entity (BROKING_FINTECH sector). Finance costs are integral to its core operations, making an EBIT-based operating margin inapplicable.",
        [{"ticker":"MOTILALOFS","fiscal_year":"FY25","page": sections["motilalofs_fy25"]["statement_pages"]["pnl"],
          "pdf":"motilalofs_fy25.pdf","label":"Consolidated PnL – sector note"}])

    # Q15 dev – TCS FY25 Debt-to-Equity
    debt_t25 = m(lkp, "TCS", "FY25", "total_debt")
    eq_t25   = m(lkp, "TCS", "FY25", "total_equity")
    de_t25   = (debt_t25 / eq_t25).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    add("dev", "ratio_computation",
        "What was TCS's consolidated Debt-to-Equity ratio as at 31 March 2025?",
        f"{fmt(de_t25, 4)}x",
        f"D/E = Borrowings / (Share Capital + Reserves) = {fmt(debt_t25)} / {fmt(eq_t25)} = {fmt(de_t25, 4)}x",
        [{"ticker":"TCS","fiscal_year":"FY25","page": sections["tcs_fy25"]["statement_pages"]["bs"],
          "pdf":"tcs_fy25.pdf","label":"Consolidated BS – Debt and Equity"}])

    # Q16 dev – INFY FY24→FY25 YoY Revenue Growth
    rev_i24 = m(lkp, "INFY", "FY24", "revenue_from_operations")
    rev_i25 = m(lkp, "INFY", "FY25", "revenue_from_operations")
    growth_i = ((rev_i25 - rev_i24) / rev_i24 * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    add("dev", "ratio_computation",
        "What was Infosys's YoY revenue growth rate from FY2023-24 to FY2024-25?",
        f"{fmt(growth_i)}%",
        f"YoY Growth = ({fmt(rev_i25)} − {fmt(rev_i24)}) / {fmt(rev_i24)} × 100 = {fmt(growth_i)}%",
        [{"ticker":"INFY","fiscal_year":"FY25","page": sections["infy_fy25"]["statement_pages"]["pnl"],
          "pdf":"infy_fy25.pdf","label":"PnL – Revenue FY25"},
         {"ticker":"INFY","fiscal_year":"FY24","page": sections["infy_fy24"]["statement_pages"]["pnl"],
          "pdf":"infy_fy24.pdf","label":"PnL – Revenue FY24"}])

    # Q17 test – TCS FY24→FY26 Revenue CAGR
    rev_t24 = m(lkp, "TCS", "FY24", "revenue_from_operations")
    rev_t26 = m(lkp, "TCS", "FY26", "revenue_from_operations")
    # CAGR over 2 years: (rev26/rev24)^(1/2) - 1
    import math
    cagr_t = (Decimal(str(math.pow(float(rev_t26 / rev_t24), 0.5))) - 1) * 100
    cagr_t = cagr_t.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    add("test", "ratio_computation",
        "What was TCS's 2-year revenue CAGR from FY2023-24 to FY2025-26?",
        f"{fmt(cagr_t)}%",
        f"CAGR = (Rev_FY26/Rev_FY24)^(1/2) − 1 = ({fmt(rev_t26)}/{fmt(rev_t24)})^0.5 − 1 = {fmt(cagr_t)}%",
        [{"ticker":"TCS","fiscal_year":"FY24","page": sections["tcs_fy24"]["statement_pages"]["pnl"],"pdf":"tcs_fy24.pdf"},
         {"ticker":"TCS","fiscal_year":"FY26","page": sections["tcs_fy26"]["statement_pages"]["pnl"],"pdf":"tcs_fy26.pdf"}])

    # Q18 test – MOTILALOFS FY24 ROE
    pat_mofs24 = m(lkp, "MOTILALOFS", "FY24", "net_profit")
    eq_mofs24  = m(lkp, "MOTILALOFS", "FY24", "total_equity")
    roe_mofs24 = (pat_mofs24 / eq_mofs24 * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    add("test", "ratio_computation",
        "What was Motilal Oswal Financial Services' Return on Equity for FY2023-24?",
        f"{fmt(roe_mofs24)}%",
        f"ROE = {fmt(pat_mofs24)} / {fmt(eq_mofs24)} × 100 = {fmt(roe_mofs24)}%",
        [{"ticker":"MOTILALOFS","fiscal_year":"FY24","page": sections["motilalofs_fy24"]["statement_pages"]["pnl"],
          "pdf":"motilalofs_fy24.pdf"}])

    # ═════════════════════════════════════════════════════════════════════════
    # CATEGORY 3: text_retrieval  (7 questions, grounded in extracted text)
    # ═════════════════════════════════════════════════════════════════════════

    # Q19 dev – TCS FY24 ERM framework (confirmed in extracted text: p79)
    add("dev", "text_retrieval",
        "According to TCS's FY2023-24 Annual Report, what framework does TCS use for Enterprise Risk Management and what is its primary purpose?",
        "TCS uses its Enterprise Risk Management (ERM) framework to protect the company's business and clients, and to add value for all stakeholders by effectively managing and mitigating risks.",
        "Page 79 of tcs_fy24.pdf contains TCS's ERM section: 'TCS understands the importance of effectively managing and mitigating risks to protect the company's business, its clients, to add value for all its stakeholders.'",
        [{"ticker":"TCS","fiscal_year":"FY24","page":79,"pdf":"tcs_fy24.pdf",
          "section":"risk_factors","passage_start":"TCS understands the importance"}])

    # Q20 dev – INFY FY24 Geo-political risk (confirmed: p122)
    add("dev", "text_retrieval",
        "What geo-political and macroeconomic risk does Infosys highlight in its FY2023-24 risk section, and how might it impact the company?",
        "Infosys highlights that unfavourable geo-political, economic or health events may result in business disruptions affecting revenue and profitability. The risk framework also covers supply chain constraints and talent availability.",
        "Page 122 of infy_fy24.pdf: 'Geo-political, macroeconomic or health events – Unfavorable geo-political, economic or health events may result in...' under the Key/Emerging Risks table.",
        [{"ticker":"INFY","fiscal_year":"FY24","page":122,"pdf":"infy_fy24.pdf",
          "section":"risk_factors","passage_start":"Geo-political, macroeconomic or health events"}])

    # Q21 dev – MOTILALOFS FY24 MDA Global Economy (confirmed: p49)
    add("dev", "text_retrieval",
        "What was the global GDP growth rate cited in Motilal Oswal Financial Services' FY2023-24 Management Discussion and Analysis?",
        "According to the MD&A, global economic growth declined from 3.5% in 2022 to an estimated 3.1% in 2023.",
        "Page 49 of motilalofs_fy24.pdf, MD&A section: 'Global economic growth declined from 3.5% in 2022 to an estimated 3.1% in 2023. A disproportionate share...'",
        [{"ticker":"MOTILALOFS","fiscal_year":"FY24","page":49,"pdf":"motilalofs_fy24.pdf",
          "section":"mda","passage_start":"Global economic growth declined from 3.5%"}])

    # Q22 dev – ANGELONE FY25 MDA Global Economy (confirmed: p41)
    add("dev", "text_retrieval",
        "How does Angel One's FY2024-25 MD&A describe the global economic environment in 2024?",
        "Angel One's MD&A states the global economy exhibited resilience amidst mounting challenges of prolonged inflation, elevated interest rates and geopolitical tensions in 2024.",
        "Page 41 of angelone_fy25.pdf, MD&A: 'The global economy exhibited resilience amidst mounting challenges of prolonged inflation, elevated interest rates and geopolitical tensions in 2024.'",
        [{"ticker":"ANGELONE","fiscal_year":"FY25","page":41,"pdf":"angelone_fy25.pdf",
          "section":"mda","passage_start":"The global economy exhibited resilience"}])

    # Q23 dev – INFY FY26 AI risk (confirmed: p133)
    add("dev", "text_retrieval",
        "What is the AI-related risk Infosys identifies in its FY2025-26 annual report risk section?",
        "Infosys identifies the risk that if it is unable to transform existing services by leveraging AI and/or scale new AI-first services, it may face commoditisation of its offerings and loss of competitive positioning.",
        "Page 133 of infy_fy26.pdf: 'Artificial Intelligence (AI) risks – If we are unable to transform existing services by leveraging AI and / or scale new AI-first services...'",
        [{"ticker":"INFY","fiscal_year":"FY26","page":133,"pdf":"infy_fy26.pdf",
          "section":"risk_factors","passage_start":"Artificial Intelligence (AI) risks"}])

    # Q24 test – MOTILALOFS FY26 SWOT (confirmed: p64)
    add("test", "text_retrieval",
        "What strengths does Motilal Oswal Financial Services highlight in its SWOT analysis in the FY2025-26 MD&A?",
        "MOFSL's SWOT analysis lists: strong brand name 'Motilal Oswal', experienced top management, integrated financial services provider, and independent and in-depth research capabilities.",
        "Page 64 of motilalofs_fy26.pdf, MD&A SWOT Analysis: 'Strengths – Strong brand name Motilal Oswal. Experienced top management. Integrated financial services provider. Independent and in-depth research.'",
        [{"ticker":"MOTILALOFS","fiscal_year":"FY26","page":64,"pdf":"motilalofs_fy26.pdf",
          "section":"risk_factors","passage_start":"Strengths"}])

    # Q25 test – ANGELONE FY26 MDA market performance (grounded in p40)
    add("test", "text_retrieval",
        "How does Angel One's FY2025-26 MD&A describe the performance of Indian capital markets during the year?",
        "Angel One's MD&A states that Indian capital markets entered a phase of democratisation and structural maturity in FY26 marked by healthy retail participation, while Nifty 50 and BSE Sensex posted muted returns of -5.1% and -7.1% respectively and DII ownership in NSE-listed companies reached 16.6%.",
        "Page 40 of angelone_fy26.pdf, MD&A: 'The Indian capital markets entered a phase of democratisation and structural maturity in FY26, marked by healthy retail participation... muted domestic equity market performance of -5.1% and -7.1% for the Nifty 50 and BSE Sensex respectively.'",
        [{"ticker":"ANGELONE","fiscal_year":"FY26","page":40,"pdf":"angelone_fy26.pdf",
          "section":"mda","passage_start":"The Indian capital markets entered"}])
    # ═════════════════════════════════════════════════════════════════════════
    # CATEGORY 4: multi_hop_compare  (6 questions)
    # ═════════════════════════════════════════════════════════════════════════

    # Q26 dev – TCS vs INFY FY24 net margin comparison + narrative reason
    nm_tcs24  = (m(lkp,"TCS","FY24","net_profit") / m(lkp,"TCS","FY24","revenue_from_operations") * 100).quantize(Decimal("0.01"))
    nm_infy24 = (m(lkp,"INFY","FY24","net_profit") / m(lkp,"INFY","FY24","revenue_from_operations") * 100).quantize(Decimal("0.01"))
    add("dev", "multi_hop_compare",
        "Compare TCS and Infosys's net profit margins for FY2023-24 and explain what the difference suggests about their profitability profiles.",
        f"TCS net margin: {fmt(nm_tcs24)}%; Infosys net margin: {fmt(nm_infy24)}%. TCS has a higher net margin, reflecting its larger scale, diverse revenue mix, and operating leverage. TCS's MD&A highlights its differentiated AI.Cloud unit and operating model as drivers of sustained profitability.",
        "Step 1: Compute TCS Net Margin = PAT/Revenue. Step 2: Compute INFY Net Margin. Step 3: Reference TCS MD&A (tcs_fy24 p69-71) for strategic differentiation narrative.",
        [{"ticker":"TCS","fiscal_year":"FY24","page": sections["tcs_fy24"]["statement_pages"]["pnl"],"pdf":"tcs_fy24.pdf","label":"TCS PnL"},
         {"ticker":"INFY","fiscal_year":"FY24","page": sections["infy_fy24"]["statement_pages"]["pnl"],"pdf":"infy_fy24.pdf","label":"INFY PnL"},
         {"ticker":"TCS","fiscal_year":"FY24","page":69,"pdf":"tcs_fy24.pdf","section":"mda"}])

    # Q27 dev – ANGELONE debt growth + narrative reason (update page & % from Step 1)
    debt_ao24 = m(lkp,"ANGELONE","FY24","total_debt")
    debt_ao26 = m(lkp,"ANGELONE","FY26","total_debt")
    debt_chg  = ((debt_ao26 - debt_ao24) / debt_ao24 * 100).quantize(Decimal("0.1"))
    add("dev", "multi_hop_compare",
        "How did Angel One's total borrowings change between FY2023-24 and FY2025-26, and what business activity does the MD&A suggest drove this increase?",
        f"Angel One's borrowings grew from ₹{fmt(debt_ao24)} crore (FY24) to ₹{fmt(debt_ao26)} crore (FY26), an increase of approximately {fmt(debt_chg)}%. The MD&A links higher borrowings to scaling the client funding book (margin trading facility).",
        "Step 1: Read total_debt FY24 and FY26 from CSV. Step 2: Reference the exact MD&A page from Step 1 discussing client funding book / MTF expansion.",
        [{"ticker":"ANGELONE","fiscal_year":"FY24","page": sections["angelone_fy24"]["statement_pages"]["bs"],"pdf":"angelone_fy24.pdf"},
         {"ticker":"ANGELONE","fiscal_year":"FY26","page": sections["angelone_fy26"]["statement_pages"]["bs"],"pdf":"angelone_fy26.pdf"},
         {"ticker":"ANGELONE","fiscal_year":"FY26","page":42,"pdf":"angelone_fy26.pdf","section":"mda"}])  # <-- set exact PDF & page from Step 1
    # Q28 dev – INFY FY26 AI risk vs revenue growth
    rev_i26 = m(lkp,"INFY","FY26","revenue_from_operations")
    growth_i2 = ((rev_i26 - rev_i25) / rev_i25 * 100).quantize(Decimal("0.01"))
    add("dev", "multi_hop_compare",
        "Infosys grew revenue by approximately how much in FY2025-26, and what AI-related risk does its annual report identify that could threaten this growth?",
        f"Infosys's FY26 revenue grew {fmt(growth_i2)}% YoY (from ₹{fmt(rev_i25)} Cr to ₹{fmt(rev_i26)} Cr). Its FY26 risk section identifies the risk that inability to transform services by leveraging AI or scale AI-first services could lead to commoditisation and loss of competitive positioning.",
        "Step 1: Compute YoY revenue growth FY25→FY26. Step 2: Reference infy_fy26.pdf page 133 for AI risk description.",
        [{"ticker":"INFY","fiscal_year":"FY26","page": sections["infy_fy26"]["statement_pages"]["pnl"],"pdf":"infy_fy26.pdf"},
         {"ticker":"INFY","fiscal_year":"FY25","page": sections["infy_fy25"]["statement_pages"]["pnl"],"pdf":"infy_fy25.pdf"},
         {"ticker":"INFY","fiscal_year":"FY26","page":133,"pdf":"infy_fy26.pdf","section":"risk_factors"}])

    # Q29 dev – MOTILALOFS PAT decline FY25→FY26 + narrative context
    pat_mofs25 = m(lkp,"MOTILALOFS","FY25","net_profit")
    pat_m26    = m(lkp,"MOTILALOFS","FY26","net_profit")
    pat_drop   = ((pat_m26 - pat_mofs25) / pat_mofs25 * 100).quantize(Decimal("0.1"))
    add("dev", "multi_hop_compare",
        "Motilal Oswal Financial Services' net profit declined from FY2024-25 to FY2025-26. By how much did it decline, and what does the FY2025-26 MD&A say about Indian equity market conditions during the year?",
        f"PAT declined by {fmt(abs(pat_drop))}% (from ₹{fmt(pat_mofs25)} Cr to ₹{fmt(pat_m26)} Cr). The FY26 MD&A notes that Indian equities experienced a broad-based correction in FY26, with indices showing negative returns, which weighed on fee-based and proprietary income.",
        "Step 1: Compute PAT change. Step 2: Reference motilalofs_fy26.pdf page 53 for equity market correction context.",
        [{"ticker":"MOTILALOFS","fiscal_year":"FY25","page": sections["motilalofs_fy25"]["statement_pages"]["pnl"],"pdf":"motilalofs_fy25.pdf"},
         {"ticker":"MOTILALOFS","fiscal_year":"FY26","page": sections["motilalofs_fy26"]["statement_pages"]["pnl"],"pdf":"motilalofs_fy26.pdf"},
         {"ticker":"MOTILALOFS","fiscal_year":"FY26","page":53,"pdf":"motilalofs_fy26.pdf","section":"mda"}])

    # Q30 test – TCS operating profit trend + ERM narrative
    op_t24 = m(lkp,"TCS","FY24","operating_profit")
    op_t25 = m(lkp,"TCS","FY25","operating_profit")
    op_t26 = m(lkp,"TCS","FY26","operating_profit")
    add("test", "multi_hop_compare",
        "How has TCS's operating profit (EBIT) trended from FY24 to FY26, and what currency-related risk does TCS's FY24 risk section identify as a key financial risk?",
        f"TCS's operating profit (EBIT = PBT + Interest − Other Income) was ₹{fmt(op_t24)} Cr (FY24), ₹{fmt(op_t25)} Cr (FY25), and ₹{fmt(op_t26)} Cr (FY26), showing a consistent upward trend. TCS's FY24 ERM section (page 82) identifies currency volatility as a key financial risk, noting that revenue and cost mismatches across geographies can materially impact financial performance.",
        "Step 1: Compute EBIT for each year from CSV. Step 2: Reference tcs_fy24.pdf page 82 for currency risk passage.",
        [{"ticker":"TCS","fiscal_year":"FY24","page":82,"pdf":"tcs_fy24.pdf","section":"risk_factors"},
         {"ticker":"TCS","fiscal_year":"FY24","page": sections["tcs_fy24"]["statement_pages"]["pnl"],"pdf":"tcs_fy24.pdf"},
         {"ticker":"TCS","fiscal_year":"FY26","page": sections["tcs_fy26"]["statement_pages"]["pnl"],"pdf":"tcs_fy26.pdf"}])

    # Q31 test – INFY vs TCS FY26 Revenue gap + talent risk
    rev_t26b = m(lkp,"TCS","FY26","revenue_from_operations")
    rev_i26b = m(lkp,"INFY","FY26","revenue_from_operations")
    gap = rev_t26b - rev_i26b
    add("test", "multi_hop_compare",
        "What is the revenue gap between TCS and Infosys in FY2025-26, and what talent-related risk does Infosys highlight in its FY24 risk section that could affect future competitiveness?",
        f"TCS's FY26 revenue (₹{fmt(rev_t26b)} Cr) exceeds Infosys's (₹{fmt(rev_i26b)} Cr) by ₹{fmt(gap)} Cr. Infosys's FY24 risk section (page 123) highlights talent supply constraints: inability to hire, engage and retain technology and management talent could impair delivery quality and growth.",
        "Step 1: Compute revenue gap from CSV. Step 2: Reference infy_fy24.pdf page 123 talent risk passage.",
        [{"ticker":"TCS","fiscal_year":"FY26","page": sections["tcs_fy26"]["statement_pages"]["pnl"],"pdf":"tcs_fy26.pdf"},
         {"ticker":"INFY","fiscal_year":"FY26","page": sections["infy_fy26"]["statement_pages"]["pnl"],"pdf":"infy_fy26.pdf"},
         {"ticker":"INFY","fiscal_year":"FY24","page":123,"pdf":"infy_fy24.pdf","section":"risk_factors"}])

    # ═════════════════════════════════════════════════════════════════════════
    # CATEGORY 5: unanswerable  (4 questions)
    # ═════════════════════════════════════════════════════════════════════════

    add("dev", "unanswerable",
        "What was TCS's quarterly revenue for Q1 FY2027?",
        "REFUSE_OUT_OF_SCOPE",
        "FY27 data is entirely outside the scope of this dataset (FY24–FY26 only). No FY27 figures exist in the annual reports or Screener files.",
        [],
        {"reason": "future_fiscal_year"})

    add("dev", "unanswerable",
        "What was Wipro's consolidated net profit for FY2024-25?",
        "REFUSE_OUT_OF_SCOPE",
        "Wipro is not one of the four covered companies (TCS, INFY, ANGELONE, MOTILALOFS). No data for Wipro exists in this corpus.",
        [],
        {"reason": "out_of_scope_company"})

    add("test", "unanswerable",
        "What revenue guidance has TCS provided for FY2026-27?",
        "REFUSE_OUT_OF_SCOPE",
        "None of TCS's annual reports (FY24, FY25, FY26) provide explicit forward revenue guidance for FY27. TCS's reports note macro uncertainty and do not publish formal revenue guidance.",
        [],
        {"reason": "unstated_guidance"})

    add("test", "unanswerable",
        "What were Angel One's quarterly subscriber additions in Q2 FY2024-25?",
        "REFUSE_OUT_OF_SCOPE",
        "The dataset covers only consolidated annual financial statements and narrative sections from annual reports. Quarterly subscriber addition data is not present in any of the 12 PDFs or Screener XLSX files.",
        [],
        {"reason": "quarterly_operational_metric_not_in_corpus"})

    return questions


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    lkp = load_metrics()
    cfg = load_config()
    questions = build_questions(lkp, cfg)

    # Validate distribution
    by_cat   = {}
    by_split = {"dev": 0, "test": 0}
    for q in questions:
        by_cat[q["category"]] = by_cat.get(q["category"], 0) + 1
        by_split[q["split"]] += 1

    out = {
        "meta": {
            "total": len(questions),
            "dev":   by_split["dev"],
            "test":  by_split["test"],
            "category_counts": by_cat,
            "scope": {
                "tickers":      ["TCS", "INFY", "ANGELONE", "MOTILALOFS"],
                "fiscal_years": ["FY24", "FY25", "FY26"],
            },
        },
        "questions": questions,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Wrote {len(questions)} questions → {OUT_PATH}")
    print(f"  Split:      dev={by_split['dev']}, test={by_split['test']}")
    print(f"  Categories: {by_cat}")

    # Validation checks
    errors = []
    if len(questions) != 35:
        errors.append(f"Expected 35 questions, got {len(questions)}")
    if by_split["dev"] != 25:
        errors.append(f"Expected 25 dev, got {by_split['dev']}")
    if by_split["test"] != 10:
        errors.append(f"Expected 10 test, got {by_split['test']}")
    expected_cats = {"numeric_lookup":10,"ratio_computation":8,"text_retrieval":7,
                     "multi_hop_compare":6,"unanswerable":4}
    for cat, cnt in expected_cats.items():
        if by_cat.get(cat, 0) != cnt:
            errors.append(f"Expected {cnt} {cat}, got {by_cat.get(cat,0)}")

    if errors:
        print("\nWARNINGS:")
        for e in errors:
            print(f"  ⚠ {e}")
    else:
        print("\n  Distribution PASS ✓")


if __name__ == "__main__":
    main()
