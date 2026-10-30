"""Project settings read from .env (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GCP_PROJECT = os.environ["GCP_PROJECT"]
BQ_LOCATION = os.environ.get("BQ_LOCATION", "asia-south1")

DATASETS = {
    "hrbench_raw": "Values as extracted from BRSR PDFs, one row per bank/year/metric/gender.",
    "hrbench_clean": "Validated, unit-checked values with data-quality flags.",
    "hrbench_marts": "Benchmark tables (ranks, peer medians, YoY, Kotak scorecard) for Power BI.",
}
