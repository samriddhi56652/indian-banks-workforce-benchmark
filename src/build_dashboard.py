"""Build the HTML dashboard from the mart CSVs.

Usage:  python src\\build_dashboard.py
Input:  data\\marts\\*.csv, dashboard\\template.html
Output: dashboard\\index.html (self-contained; open it in any browser)
"""
import json
from datetime import date

import pandas as pd

from config import ROOT

MARTS = ROOT / "data" / "marts"
TEMPLATE = ROOT / "dashboard" / "template.html"
OUT = ROOT / "dashboard" / "index.html"


def records(df):
    return json.loads(df.to_json(orient="records"))


def main():
    benchmark = pd.read_csv(MARTS / "benchmark.csv")
    scorecard = pd.read_csv(MARTS / "kotak_scorecard.csv")
    tvt = pd.read_csv(MARTS / "training_vs_turnover.csv")
    extracted = pd.read_csv(ROOT / "data" / "raw" / "brsr_extracted.csv", usecols=["source_file"])

    data = {
        "benchmark": records(benchmark),
        "scorecard": records(scorecard),
        "tvt": records(tvt),
        "meta": {"n_values": len(extracted), "n_reports": extracted["source_file"].nunique(),
                 "built": date.today().isoformat()},
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data))
    OUT.write_text(html, encoding="utf-8")
    print(f"Dashboard -> {OUT.relative_to(ROOT)}  ({len(html) // 1024} KB, {len(benchmark)} benchmark rows)")


if __name__ == "__main__":
    main()
