"""Create the project's BigQuery datasets. Safe to re-run."""
from google.cloud import bigquery

from config import BQ_LOCATION, DATASETS, GCP_PROJECT


def main():
    client = bigquery.Client(project=GCP_PROJECT, location=BQ_LOCATION)
    for name, description in DATASETS.items():
        ds = bigquery.Dataset(f"{GCP_PROJECT}.{name}")
        ds.location = BQ_LOCATION
        ds.description = description
        ds = client.create_dataset(ds, exists_ok=True)
        # exists_ok does not change an existing dataset's location, so check it
        if ds.location != BQ_LOCATION:
            raise SystemExit(f"{name} exists in {ds.location}, expected {BQ_LOCATION}")
        print(f"OK  {ds.dataset_id}  ({ds.location})")


if __name__ == "__main__":
    main()
