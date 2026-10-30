"""Extract the target BRSR tables from all reports into one long, tidy CSV.

Usage:  python src\\extract_brsr.py
Input:  data\\raw\\brsr\\*_FY??_BRSR.pdf and data\\page_index.csv (from locate_tables.py)
        data\\raw\\manual_entry.csv (values typed in by hand where extraction fails)
Output: data\\raw\\brsr_extracted.csv, data\\raw\\missing_values.csv

One row per bank x fiscal_year x metric x gender. Every value keeps the file,
the PDF page (1-based index) and the text exactly as printed (raw).
"""
import re

import pandas as pd
import pdfplumber

from config import ROOT

RAW_DIR = ROOT / "data" / "raw" / "brsr"
PAGE_INDEX = ROOT / "data" / "page_index.csv"
MANUAL_FILE = ROOT / "data" / "raw" / "manual_entry.csv"
OUT_FILE = ROOT / "data" / "raw" / "brsr_extracted.csv"
MISSING_FILE = ROOT / "data" / "raw" / "missing_values.csv"

COLUMNS = ["bank", "fiscal_year", "metric", "gender", "value", "unit",
           "source_file", "page", "raw", "method", "note"]

# A number as printed: 1,54,983 / 104,332 / 72.6% / 0.14%* / 03; or a "no value" marker.
TOKEN = re.compile(r"^(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?%?$|^(?:-|–|nil|na|n\.a\.?|not applicable)$", re.I)
MISSING_MARKERS = {"-", "–", "nil", "na", "n.a", "n.a."}
FOOTNOTE = "*#¹²³†"


def fiscal_years(file_fy):
    """FY26 -> ['FY2025-26', 'FY2024-25', 'FY2023-24'] (current, previous, prior)."""
    end = 2000 + int(file_fy[2:])
    return [f"FY{end - k - 1}-{str(end - k)[-2:]}" for k in range(3)]


def numbers_after(text):
    """Leading numeric tokens of `text`, stopping at the first word (handles
    two-column pages where unrelated text follows the numbers)."""
    text = re.sub(r"(\d)\s+%", r"\1%", text)          # "100 %" -> "100%"
    text = re.sub(r"(\d),\s+(\d{3})\b", r"\1,\2", text)  # "36, 546" -> "36,546"
    out = []
    for tok in text.split():
        tok = tok.strip(FOOTNOTE)
        if not tok:
            continue
        if TOKEN.match(tok):
            out.append(tok)
        else:
            break
    return out


def to_value(tok):
    if tok is None or tok.lower().rstrip(".") in MISSING_MARKERS:
        return None
    return float(tok.rstrip("%").replace(",", ""))


class Report:
    """Text lines of the pages where one report's target tables sit."""

    def __init__(self, path, pages):
        self.lines = []  # (page_no, line)
        with pdfplumber.open(path) as pdf:
            for p in sorted(pages):
                if 1 <= p <= len(pdf.pages):
                    for line in (pdf.pages[p - 1].extract_text() or "").splitlines():
                        self.lines.append((p, line))

    def find(self, pattern, start=0):
        """Index of the first line at or after `start` matching `pattern`."""
        rx = re.compile(pattern, re.I)
        for i in range(start, len(self.lines)):
            if rx.search(self.lines[i][1]):
                return i
        return None

    def row(self, label, start, min_tokens=1, within=40, wrap=False):
        """Numbers on the first line after `start` whose label matches and that
        has at least `min_tokens` numbers. Returns (tokens, page) or (None, None)."""
        if start is None:
            return None, None
        rx = re.compile(label, re.I)
        for i in range(start, min(start + within, len(self.lines))):
            page, line = self.lines[i]
            m = rx.search(line)
            if m:
                toks = numbers_after(line[m.end():])
                if len(toks) >= min_tokens:
                    return toks, page
                # a long label can wrap: the numbers then start the next line
                if wrap and i + 1 < len(self.lines):
                    page, nxt = self.lines[i + 1]
                    toks = numbers_after(nxt)
                    if len(toks) >= min_tokens:
                        return toks, page
        return None, None


def extract_file(path, first_pages):
    bank, file_fy = path.stem.split("_")[:2]
    years = fiscal_years(file_fy)
    pages = {p for p in first_pages.values() if p} | {p + 1 for p in first_pages.values() if p}
    rep = Report(path, pages)
    rows = []

    def add(metric, gender, tok, unit, page, year=years[0], note=""):
        rows.append({"bank": bank, "fiscal_year": year, "metric": metric, "gender": gender,
                     "value": to_value(tok), "unit": unit, "source_file": path.name, "page": page,
                     "raw": tok, "method": "auto", "note": note})

    def heading(pattern):
        return rep.find(pattern)

    # --- Section A Q20a: headcount (Total, Male no., %, Female no., %, [Other no., %])
    h = heading(r"employees(?: and workers)?\d*\W{0,3}\(?including differently")
    labels = {
        "headcount_permanent": r"permanent\s*\(D\)[\d*#¹²]*",
        "headcount_other_than_permanent": r"other than permanent\s*\(E\)[\d*#¹²]*",
        "headcount_total": r"total employees\s*\(D\s*\+\s*E\)[\d*#¹²]*",
    }
    for metric, label in labels.items():
        toks, page = rep.row(label, h, min_tokens=5, within=15)
        if toks:
            add(metric, "total", toks[0], "count", page)
            add(metric, "male", toks[1], "count", page)
            add(metric, "female", toks[3], "count", page)
            if len(toks) >= 6:
                add(metric, "other", toks[5], "count", page)

    # --- Section A Q20b: differently abled permanent employees
    h = heading(r"differently\W{0,3}abled employees")
    toks, page = rep.row(labels["headcount_permanent"], h, min_tokens=5, within=15)
    if toks:
        add("differently_abled_permanent", "total", toks[0], "count", page)
        add("differently_abled_permanent", "male", toks[1], "count", page)
        add("differently_abled_permanent", "female", toks[3], "count", page)

    # --- Section A Q21: women on Board and in KMP (Total, No. of females, %)
    h = heading(r"participation\W{0,3}inclusion\W{0,3}representation of women")
    # footnote markers only: a digit here would swallow the first number of the row
    for metric, label in {"board_members": r"board of directors(?:\s*\(BoD\))?[*#¹²]*",
                          "kmp_members": r"key manag\w* personnel(?:\s*\(KMP\))?[*#¹²]*"}.items():
        toks, page = rep.row(label, h, min_tokens=2, within=12)
        if toks:
            add(metric, "total", toks[0], "count", page)
            add(metric, "female", toks[1], "count", page)

    # --- Section A Q22: turnover, 3 years x (Male, Female, [Other], Total)
    h = heading(r"turnover rate for permanent employees")
    toks, page = rep.row(r"^\W*permanent(?! workers)(?:\s+employees?)?(?:\s*\(%\))?[\d*#¹²]*", h, min_tokens=9, within=16)
    if toks:
        genders = ["male", "female", "other", "total"] if len(toks) >= 12 else ["male", "female", "total"]
        for k, year in enumerate(years):
            for j, g in enumerate(genders):
                add("turnover_rate_permanent", g, toks[k * len(genders) + j], "%", page, year)

    # --- P3 Q1a: well-being coverage, permanent employees, Total row
    # (Total, Health no., %, Accident no., %, Maternity no., %, Paternity no., %, Day care no., %)
    h = heading(r"measures? for the well\W{0,3}being of employees")
    toks, page = rep.row(r"^\W*total", h, min_tokens=11, within=20)
    if toks:
        for metric, pos in {"wellbeing_health_insurance": 2, "wellbeing_accident_insurance": 4,
                            "wellbeing_maternity": 6, "wellbeing_paternity": 8, "wellbeing_day_care": 10}.items():
            add(metric, "total", toks[pos], "%", page, note="permanent employees; % of all permanent employees")

    # --- P3 Q1c: well-being spend as % of revenue (current, previous)
    i = heading(r"cost incurred on well\W{0,3}being measures")
    toks, page = rep.row(r"cost incurred on well\W{0,3}being measures[^0-9]*", i, min_tokens=1, within=1, wrap=True)
    if toks:
        for k, tok in enumerate(toks[:2]):
            add("wellbeing_spend_pct_revenue", "total", tok, "%", page, years[k])

    # --- P3 Q5: parental leave (Return to work rate, Retention rate), permanent employees
    h = heading(r"return to work and retention rates")
    for g in ["male", "female", "total"]:
        toks, page = rep.row(rf"^\W*{g}\b", h, min_tokens=2, within=12)
        if toks:
            add("parental_return_to_work_rate", g, toks[0], "%", page)
            add("parental_retention_rate", g, toks[1], "%", page)

    # --- P3 Q8: training (Total A, H&S no., %, Skill no., %) x current, previous
    h = heading(r"details of training.{0,4}given to employees")
    for g in ["male", "female", "total"]:
        toks, page = rep.row(rf"^\W*{g}\b", h, min_tokens=5, within=14)
        if toks:
            for k in range(len(toks) // 5):
                base = k * 5
                add("training_base", g, toks[base], "count", page, years[k])
                add("training_health_safety_pct", g, toks[base + 2], "%", page, years[k])
                add("training_skill_upgradation_pct", g, toks[base + 4], "%", page, years[k])

    # --- P3 Q9: performance & career development reviews (Total A, No. B, %) x current, previous
    h = heading(r"performance and career development reviews")
    for g in ["male", "female", "total"]:
        # HDFC puts a long description before the table, so look further ahead
        toks, page = rep.row(rf"^\W*{g}\b", h, min_tokens=3, within=40)
        if toks:
            for k in range(min(len(toks) // 3, 2)):
                add("review_base", g, toks[k * 3], "count", page, years[k])
                add("review_pct", g, toks[k * 3 + 2], "%", page, years[k])

    # --- P5 Q3b: gross wages paid to females as % of total wages (current, previous)
    q3b = heading(r"gross wages paid to females")
    toks, page = rep.row(r"gross wages paid to females as % of[^0-9]*", q3b, min_tokens=1, within=8)
    if toks:
        for k, tok in enumerate(toks[:2]):
            add("female_wages_pct_of_total", "total", tok, "%", page, years[k])

    # --- P5 Q6: sexual harassment complaints, current year (Filed, Pending)
    h = rep.find(r"number of complaints on the following made by employees", q3b or 0)
    toks, page = rep.row(r"^\W*sexual harassment", h, min_tokens=2, within=10)
    if toks:
        add("complaints_sexual_harassment_filed", "total", toks[0], "count", page)
        add("complaints_sexual_harassment_pending", "total", toks[1], "count", page)

    return rows


# Earlier years printed in a report are kept (useful context) but not required.
STUDY_YEARS = {"FY2023-24", "FY2024-25", "FY2025-26"}

# What we expect from every report: (metric, genders, number of years in the table)
EXPECTED = [
    ("headcount_permanent", ["male", "female", "total"], 1),
    ("headcount_other_than_permanent", ["male", "female", "total"], 1),
    ("headcount_total", ["male", "female", "total"], 1),
    ("differently_abled_permanent", ["male", "female", "total"], 1),
    ("board_members", ["female", "total"], 1),
    ("kmp_members", ["female", "total"], 1),
    ("turnover_rate_permanent", ["male", "female", "total"], 3),
    ("wellbeing_health_insurance", ["total"], 1),
    ("wellbeing_accident_insurance", ["total"], 1),
    ("wellbeing_maternity", ["total"], 1),
    ("wellbeing_paternity", ["total"], 1),
    ("wellbeing_day_care", ["total"], 1),
    ("wellbeing_spend_pct_revenue", ["total"], 2),
    ("parental_return_to_work_rate", ["male", "female", "total"], 1),
    ("parental_retention_rate", ["male", "female", "total"], 1),
    ("training_base", ["male", "female", "total"], 2),
    ("training_health_safety_pct", ["male", "female", "total"], 2),
    ("training_skill_upgradation_pct", ["male", "female", "total"], 2),
    ("review_base", ["male", "female", "total"], 2),
    ("review_pct", ["male", "female", "total"], 2),
    ("female_wages_pct_of_total", ["total"], 2),
    ("complaints_sexual_harassment_filed", ["total"], 1),
    ("complaints_sexual_harassment_pending", ["total"], 1),
]

COUNT_METRICS = ("headcount", "differently_abled", "board", "kmp", "training_base", "review_base", "complaints")
UNITS = {m: ("count" if m.startswith(COUNT_METRICS) else "%") for m, _, _ in EXPECTED}

METRIC_FIELD = {  # which located heading each metric's page comes from
    "headcount": "a_q20_headcount", "differently": "a_q20_headcount", "board": "a_q21_women_board_kmp",
    "kmp": "a_q21_women_board_kmp", "turnover": "a_q22_turnover", "wellbeing_spend": "p3_q1c_wellbeing_spend",
    "wellbeing": "p3_q1a_wellbeing", "parental": "p3_q5_parental_leave", "training": "p3_q8_training",
    "review": "p3_q9_reviews", "female_wages": "p5_q3b_female_wages", "complaints": "p5_q6_complaints",
}


def field_for(metric):
    return next(f for prefix, f in METRIC_FIELD.items() if metric.startswith(prefix))


def main():
    index = pd.read_csv(PAGE_INDEX)
    auto, missing = [], []
    for source_file, g in index.groupby("source_file"):
        first_pages = {r.field: (int(r.first_page) if pd.notna(r.first_page) else None) for r in g.itertuples()}
        rows = extract_file(RAW_DIR / source_file, first_pages)
        auto += rows
        got = {(r["metric"], r["gender"], r["fiscal_year"]) for r in rows}
        bank, file_fy = source_file.split("_")[:2]
        years = fiscal_years(file_fy)
        for metric, genders, n_years in EXPECTED:
            for year in [y for y in years[:n_years] if y in STUDY_YEARS]:
                for gender in genders:
                    if (metric, gender, year) not in got:
                        missing.append({"bank": bank, "fiscal_year": year, "metric": metric, "gender": gender,
                                        "source_file": source_file, "page": first_pages.get(field_for(metric)),
                                        "reason": "not extracted automatically"})
        print(f"{source_file:<24} extracted {len(rows):>3} values")

    df = pd.DataFrame(auto, columns=COLUMNS)

    # First run: write a template of the gaps for hand entry (fill `raw` and `value`;
    # write "not disclosed" in `raw` and leave `value` empty if the report has no figure).
    if not MANUAL_FILE.exists():
        template = pd.DataFrame(missing).drop(columns="reason").reindex(columns=COLUMNS)
        template["unit"] = template["metric"].map(UNITS)
        template["method"] = "manual"
        template.to_csv(MANUAL_FILE, index=False)
        print(f"Wrote manual-entry template with {len(template)} rows -> {MANUAL_FILE.relative_to(ROOT)}")

    # Manual entries fill gaps (and may override an auto value). Rows without `raw` are still to do.
    if MANUAL_FILE.exists():
        # keep_default_na=False so a typed "NA" stays text; value is parsed separately
        manual = pd.read_csv(MANUAL_FILE, dtype=str, keep_default_na=False)
        manual = manual[manual["raw"].str.strip() != ""]
        manual["value"] = pd.to_numeric(manual["value"], errors="coerce")
        manual["page"] = pd.to_numeric(manual["page"], errors="coerce")
        if len(manual):
            manual["method"] = "manual"
            key = ["source_file", "fiscal_year", "metric", "gender"]
            df = df.merge(manual[key].assign(_manual=True), on=key, how="left")
            df = df[df["_manual"].isna()].drop(columns="_manual")
            df = pd.concat([df, manual[COLUMNS]], ignore_index=True)
            done = set(map(tuple, manual[key].values))
            missing = [m for m in missing if (m["source_file"], m["fiscal_year"], m["metric"], m["gender"]) not in done]

    df = df.sort_values(["bank", "fiscal_year", "metric", "gender", "source_file"]).reset_index(drop=True)
    df.to_csv(OUT_FILE, index=False)
    miss = pd.DataFrame(missing, columns=["bank", "fiscal_year", "metric", "gender", "source_file", "page", "reason"])
    miss.to_csv(MISSING_FILE, index=False)

    print(f"\n{len(df)} values -> {OUT_FILE.relative_to(ROOT)}  "
          f"(auto {int((df['method'] == 'auto').sum())}, manual {int((df['method'] == 'manual').sum())}, "
          f"printed as '-'/NA {int(df['value'].isna().sum())})")
    print(f"{len(miss)} expected values not found -> {MISSING_FILE.relative_to(ROOT)}")
    if len(miss):
        print(miss.groupby(["source_file", "metric"]).size().rename("n_missing").to_string())


if __name__ == "__main__":
    main()
