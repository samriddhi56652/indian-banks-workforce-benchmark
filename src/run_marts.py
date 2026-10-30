"""Build the benchmark marts in BigQuery from sql\\*.sql, check them, and export to data\\marts\\.

Usage:  python src\\run_marts.py
Checks: ranks run 1..n within each metric-year; the peer median recomputed in pandas
matches BigQuery; every metric uses one unit.
"""
import pandas as pd
from google.cloud import bigquery

from config import BQ_LOCATION, GCP_PROJECT, ROOT

SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "data" / "marts"
MARTS = ["headline_metrics", "benchmark", "kotak_scorecard", "training_vs_turnover"]


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
    return ok


def main():
    client = bigquery.Client(project=GCP_PROJECT, location=BQ_LOCATION)
    for path in sorted(SQL_DIR.glob("*.sql")):
        client.query(path.read_text(encoding="utf-8").format(project=GCP_PROJECT)).result()
        print(f"built  {path.name}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = {}
    for mart in MARTS:
        df = client.query(f"SELECT * FROM `{GCP_PROJECT}.hrbench_marts.{mart}`").to_dataframe()
        sort = [c for c in ["metric", "fiscal_year", "rank_in_year", "bank"] if c in df.columns]
        df = df.sort_values(sort).reset_index(drop=True)
        df.to_csv(OUT_DIR / f"{mart}.csv", index=False)
        frames[mart] = df
        print(f"export {mart:<22} {len(df):>4} rows -> data\\marts\\{mart}.csv")

    print()
    b, h = frames["benchmark"], frames["headline_metrics"]

    # 1. Ranks: with RANK, the smallest is 1 and none exceeds the number of banks
    g = b.groupby(["metric", "fiscal_year"])["rank_in_year"]
    check("ranks start at 1 and stay within n", bool(((g.min() == 1) & (g.max() <= g.size())).all()))
    ties = b.duplicated(["metric", "fiscal_year", "rank_in_year"], keep=False).sum()
    print(f"      tied rows (same rank shared): {ties}")

    # 2. Peer median recomputed in pandas (peers = all banks except Kotak)
    peers = h[(h["bank"] != "KOTAK") & h["value"].notna()]
    pd_median = peers.groupby(["metric", "fiscal_year"])["value"].median().rename("pandas_median")
    sql_median = b.groupby(["metric", "fiscal_year"])["peer_median"].first()
    cmp = pd.concat([pd_median, sql_median], axis=1).dropna()
    diff = (cmp["pandas_median"] - cmp["peer_median"]).abs().max()
    check("peer median: pandas == BigQuery", diff < 1e-9, f"max diff {diff:.2e} over {len(cmp)} metric-years")

    # 3. One unit per metric
    check("one unit per metric", bool((h.groupby("metric")["unit"].nunique() == 1).all()))


if __name__ == "__main__":
    main()
