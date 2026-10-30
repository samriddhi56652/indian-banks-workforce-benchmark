"""Find the BRSR tables we extract in each report and record their PDF page numbers.

Usage:  python src\\locate_tables.py
Output: data\\page_index.csv (one row per file x field) and a summary on screen.
Pages are 1-based PDF page indexes, not the numbers printed on the pages.
"""
import re
from pathlib import Path

import pandas as pd
import pypdfium2 as pdfium

from config import ROOT

RAW_DIR = ROOT / "data" / "raw" / "brsr"
OUT_FILE = ROOT / "data" / "page_index.csv"

# Any character may stand in for a hyphen or space, because some PDFs
# encode them as unusual glyphs (e.g. "well�being").
SEP = r"[\s\W_]{0,3}"

# Banks word and number these headings slightly differently (e.g. HDFC: "Employees
# (including differently abled)" as Q25; ICICI: "training¹"), so patterns allow
# optional words and footnote markers.
FIELDS = {
    "fy_stated": r"financial year for which reporting is being done",
    "a_q20_headcount": r"employees(?: and workers)?\d*" + SEP + r"\(?including differently" + SEP + r"abled",
    "a_q21_women_board_kmp": r"participation" + SEP + r"inclusion" + SEP + r"representation of women",
    "a_q22_turnover": r"turnover rate for permanent employees",
    "p3_q1a_wellbeing": r"measures? for the well" + SEP + r"being of employees",
    "p3_q1c_wellbeing_spend": r"cost incurred on well" + SEP + r"being measures",
    "p3_q5_parental_leave": r"return to work and retention rates",
    "p3_q8_training": r"details of training.{0,4}given to employees",
    "p3_q9_reviews": r"performance and career development reviews",
    "p5_q3b_female_wages": r"gross wages paid to females",
    "p5_q6_complaints": r"number of complaints on the following made by employees",
}
# P3 also has a question worded "Number of complaints on the following made by
# employees". P5 Q6 always follows P5 Q3b, so complaints only count from there on.
AFTER = {"p5_q6_complaints": "p5_q3b_female_wages"}

FY_PATTERNS = [
    # "... being done5 FY 2025-26" (footnote digit before the year is allowed)
    re.compile(r"reporting is being done\W*\d*\W*(?:FY\s*)?(20\d\d)\s*[-–]\s*(\d{2,4})", re.I),
    # "... being done: April 1, 2025 to March 31, 2026" / "April 2023 to March 2024"
    re.compile(r"reporting is being done.{0,80}?April (?:1,? )?(20\d\d).{0,40}?March (?:31,? )?(20\d\d)", re.I),
]


def fiscal_year(text):
    for pattern in FY_PATTERNS:
        if m := pattern.search(text):
            start, end = m.groups()
            return f"{start}-{end[-2:]}"
    return None


def page_texts(path):
    pdf = pdfium.PdfDocument(path)
    try:
        for i in range(len(pdf)):
            text = pdf[i].get_textpage().get_text_range()
            yield i + 1, re.sub(r"\s+", " ", text)
    finally:
        pdf.close()


def scan(path):
    bank, fy = path.stem.split("_")[:2]
    hits = {name: [] for name in FIELDS}
    n_pages, empty, fy_stated = 0, 0, None
    for page_no, text in page_texts(path):
        n_pages = page_no
        if len(text.strip()) < 20:
            empty += 1
        for name, pattern in FIELDS.items():
            if re.search(pattern, text, re.I):
                hits[name].append(page_no)
        if fy_stated is None:
            fy_stated = fiscal_year(text)
    # The BRSR starts where Section A states the reporting year; ignore earlier
    # mentions (contents pages, ESG highlights) when picking each field's page.
    brsr_start = hits["fy_stated"][0] if hits["fy_stated"] else 1
    first = {}
    for name, pages in hits.items():
        start = first.get(AFTER.get(name)) or brsr_start
        first[name] = next((p for p in pages if p >= start), None)
    rows = [
        {"bank": bank, "file_fy": fy, "source_file": path.name, "field": name,
         "first_page": first[name], "all_pages": " ".join(map(str, pages))}
        for name, pages in hits.items()
    ]
    summary = {"bank": bank, "file_fy": fy, "pages": n_pages, "empty_pages": empty, "fy_stated": fy_stated,
               "fields_found": sum(bool(p) for p in hits.values()), "fields_total": len(FIELDS)}
    return rows, summary


def main():
    files = sorted(RAW_DIR.glob("*_FY??_BRSR.pdf"))
    all_rows, summaries = [], []
    for path in files:
        rows, summary = scan(path)
        all_rows += rows
        summaries.append(summary)
        print(f"{path.name:<24} pages={summary['pages']:<4} empty={summary['empty_pages']:<3} "
              f"fy_stated={summary['fy_stated']!s:<9} found {summary['fields_found']}/{summary['fields_total']}")

    index = pd.DataFrame(all_rows)
    index.to_csv(OUT_FILE, index=False)

    grid = index.pivot_table(index=["bank", "file_fy"], columns="field", values="first_page", aggfunc="first")
    pd.set_option("display.width", 250)
    print("\nFirst page where each field's heading appears (blank = not found):")
    print(grid.reindex(columns=list(FIELDS)).astype("Int64").to_string())
    print(f"\nSaved {len(index)} rows to {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
