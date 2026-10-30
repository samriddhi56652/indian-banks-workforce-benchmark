"""Pick one value per bank x fiscal_year x metric x gender and attach data-quality flags.

Usage:  python src\\build_clean.py
Input:  data\\raw\\brsr_extracted.csv (every report's version of every value)
Output: data\\clean\\brsr_clean.csv

Rule: when the same year appears in more than one report, the latest report wins,
because it reflects any restatement. If an earlier report printed a different
figure (beyond rounding), the row is flagged `restated` and the old value kept in a note.
"""
import pandas as pd

from config import ROOT

RAW = ROOT / "data" / "raw" / "brsr_extracted.csv"
OUT = ROOT / "data" / "clean" / "brsr_clean.csv"
STUDY_YEARS = ["FY2023-24", "FY2024-25", "FY2025-26"]

# Differences up to these sizes are rounding (HDFC prints whole-number %), not restatements.
PCT_TOLERANCE = 0.51       # percentage points
COUNT_TOLERANCE = 0.005    # 0.5% of the value

# Comparability caveats found while reading the reports (see INTERVIEW_NOTES.md).
CAVEATS = {
    ("*", "turnover_rate_permanent"): "Calculation method not stated in the report",
    ("KOTAK", "turnover_rate_permanent"): "Leavers / average of opening and closing headcount, per BRSR guidance (FY26 report p. 436)",
    ("INDUSIND", "turnover_rate_permanent"): "Method changed in FY26 report; all years taken from FY26 report (earlier reports gave gender shares of the total, not gender rates)",
    ("KOTAK", "training"): "Base = all employees incl. fixed-term (other banks: permanent employees)",
    ("YES", "review"): "Method amended in FY26 report (includes KMPs); FY2024-25 restated",
    ("HDFC", "*"): "HDFC prints % as whole numbers",
}


def caveat(bank, metric):
    notes = []
    for (b, m), text in CAVEATS.items():
        if b in (bank, "*") and (m == "*" or metric.startswith(m)):
            if b == "*" and (bank, m) in CAVEATS:
                continue  # a bank-specific note replaces the generic one
            notes.append(text)
    return "; ".join(notes)


def main():
    raw = pd.read_csv(RAW, dtype={"raw": str}, keep_default_na=False)
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw = raw[raw["fiscal_year"].isin(STUDY_YEARS)].copy()
    raw["report_fy"] = raw["source_file"].str.extract(r"_FY(\d\d)_")[0].astype(int)

    rows = []
    for key, g in raw.groupby(["bank", "fiscal_year", "metric", "gender"]):
        g = g.sort_values("report_fy", ascending=False)
        best = g.iloc[0].to_dict()
        restated, older = False, []
        for _, r in g.iloc[1:].iterrows():
            a, b = best["value"], r["value"]
            if pd.isna(a) or pd.isna(b):
                differs = pd.isna(a) != pd.isna(b)
            elif best["unit"] == "%":
                differs = abs(a - b) > PCT_TOLERANCE
            else:
                differs = abs(a - b) > COUNT_TOLERANCE * max(abs(a), 1)
            if differs:
                restated = True
                older.append(f"{r['raw']} in {r['source_file']} p.{r['page']}")
        best["restated"] = restated
        best["restated_from"] = "; ".join(older)
        best["n_reports"] = len(g)
        best["status"] = "reported" if pd.notna(best["value"]) else "not disclosed"
        best["caveat"] = caveat(best["bank"], best["metric"])
        rows.append(best)

    clean = pd.DataFrame(rows).drop(columns=["report_fy"])
    clean = clean.sort_values(["metric", "fiscal_year", "bank", "gender"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(OUT, index=False)

    print(f"{len(raw)} in-scope raw rows -> {len(clean)} clean rows -> {OUT.relative_to(ROOT)}")
    print(f"reported: {(clean['status'] == 'reported').sum()}, not disclosed: {(clean['status'] == 'not disclosed').sum()}, "
          f"restated: {int(clean['restated'].sum())}")
    r = clean[clean["restated"]]
    if len(r):
        print("\nRestated values (latest report used):")
        print(r[["bank", "fiscal_year", "metric", "gender", "raw", "source_file", "restated_from"]].to_string(index=False))


if __name__ == "__main__":
    main()
