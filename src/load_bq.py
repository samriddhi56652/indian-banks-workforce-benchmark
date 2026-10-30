"""Load the extracted (raw) and clean CSVs into BigQuery. Safe to re-run (WRITE_TRUNCATE).

Usage:  python src\\load_bq.py
Tables: hrbench_raw.brsr_extracted, hrbench_clean.brsr_clean
"""
import pandas as pd
from google.cloud import bigquery

from config import BQ_LOCATION, GCP_PROJECT, ROOT

S, F, I, B = "STRING", "FLOAT64", "INT64", "BOOL"
BASE = [("bank", S), ("fiscal_year", S), ("metric", S), ("gender", S), ("value", F), ("unit", S),
        ("source_file", S), ("page", I), ("raw", S), ("method", S), ("note", S)]

TABLES = {
    "hrbench_raw.brsr_extracted": (ROOT / "data" / "raw" / "brsr_extracted.csv", BASE),
    "hrbench_clean.brsr_clean": (ROOT / "data" / "clean" / "brsr_clean.csv",
                                 BASE + [("restated", B), ("restated_from", S), ("n_reports", I),
                                         ("status", S), ("caveat", S)]),
}


def read(path, schema):
    # keep_default_na=False: a printed "NA" must stay text in `raw`
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col, typ in schema:
        if typ == F:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif typ == I:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        elif typ == B:
            df[col] = df[col].map({"True": True, "False": False})
        else:
            df[col] = df[col].replace("", None)
    return df[[c for c, _ in schema]]


def main():
    client = bigquery.Client(project=GCP_PROJECT, location=BQ_LOCATION)
    for table, (path, schema) in TABLES.items():
        df = read(path, schema)
        job_config = bigquery.LoadJobConfig(
            schema=[bigquery.SchemaField(c, t) for c, t in schema],
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        client.load_table_from_dataframe(df, f"{GCP_PROJECT}.{table}", job_config=job_config).result()
        n_bq = client.get_table(f"{GCP_PROJECT}.{table}").num_rows
        n_csv = sum(1 for _ in open(path, encoding="utf-8")) - 1
        status = "PASS" if n_csv == len(df) == n_bq else "FAIL"
        print(f"{status}  {table:<28} csv={n_csv}  pandas={len(df)}  bigquery={n_bq}")


if __name__ == "__main__":
    main()
