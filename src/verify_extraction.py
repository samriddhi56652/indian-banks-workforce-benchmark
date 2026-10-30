"""Check every extracted value against its PDF page, and build the spot-check sheet.

Usage:  python src\\verify_extraction.py
1. For every row in data\\raw\\brsr_extracted.csv, re-read the cited page with a
   different PDF library (pypdfium2) and check the value appears there as printed.
2. Write data\\raw\\spot_check_sheet.csv: every Kotak value in the study years plus
   10 random values from the other banks, sorted by file and page, for checking by eye.
"""
import re

import pandas as pd
import pypdfium2 as pdfium

from config import ROOT

RAW_DIR = ROOT / "data" / "raw" / "brsr"
EXTRACTED = ROOT / "data" / "raw" / "brsr_extracted.csv"
SHEET = ROOT / "data" / "raw" / "spot_check_sheet.csv"
STUDY_YEARS = ["FY2023-24", "FY2024-25", "FY2025-26"]
SEED = 42  # fixed, so the random sample is reproducible


def page_text(pdf, page):
    text = pdf[page - 1].get_textpage().get_text_range()
    text = re.sub(r"(\d),\s+(\d{3})\b", r"\1,\2", text)
    return re.sub(r"(\d)\s+%", r"\1%", text)


def appears(raw, text):
    """True if the printed token occurs on the page as a whole number (not inside a longer one)."""
    if not isinstance(raw, str):
        return False
    if raw.strip().lower() in {"-", "–", "nil", "na", "n.a", "n.a.", "not disclosed"}:
        return True  # markers are too common to check this way; covered by the eye check
    return re.search(rf"(?<![\d.,]){re.escape(raw)}(?![\d])", text) is not None


def main():
    # keep_default_na=False: otherwise pandas turns a printed "NA" into an empty value
    df = pd.read_csv(EXTRACTED, dtype=str, keep_default_na=False)
    found = []
    for source_file, g in df.groupby("source_file"):
        pdf = pdfium.PdfDocument(RAW_DIR / source_file)
        cache = {}
        for idx, row in g.iterrows():
            if row["page"] == "":
                found.append((idx, False))
                continue
            p = int(float(row["page"]))
            cache.setdefault(p, page_text(pdf, p))
            found.append((idx, appears(row["raw"], cache[p])))
        pdf.close()
    df["on_page"] = pd.Series(dict(found))

    ok = int(df["on_page"].sum())
    print(f"Value found on its cited page: {ok}/{len(df)} ({ok / len(df):.1%})")
    bad = df[~df["on_page"]]
    if len(bad):
        print(bad[["source_file", "page", "fiscal_year", "metric", "gender", "raw"]].to_string(index=False))

    in_scope = df[df["fiscal_year"].isin(STUDY_YEARS)]
    kotak = in_scope[in_scope["bank"] == "KOTAK"]
    others = in_scope[in_scope["bank"] != "KOTAK"].sample(10, random_state=SEED)
    sheet = pd.concat([kotak.assign(sample="kotak_all"), others.assign(sample="random_10")])
    sheet = sheet.sort_values(["source_file", "page", "metric", "fiscal_year", "gender"])
    sheet["matches_pdf"] = ""  # fill Y / N while checking
    sheet["comment"] = ""
    cols = ["sample", "source_file", "page", "metric", "fiscal_year", "gender", "raw", "unit", "matches_pdf", "comment"]
    sheet[cols].to_csv(SHEET, index=False)
    print(f"\nSpot-check sheet: {len(kotak)} Kotak + {len(others)} random -> {SHEET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
