"""Check BigQuery access and that the project datasets exist in the right location."""
import sys

from google.cloud import bigquery

from config import BQ_LOCATION, DATASETS, GCP_PROJECT


def main():
    client = bigquery.Client(project=GCP_PROJECT, location=BQ_LOCATION)

    # A trivial query proves credentials, quota project and the BigQuery API all work
    result = list(client.query("SELECT 1 AS ok").result())
    print(f"Project: {client.project}  |  test query returned {result[0].ok}")

    found = {ds.dataset_id: ds for ds in client.list_datasets()}
    failed = False
    for name in DATASETS:
        if name not in found:
            print(f"MISSING  {name}")
            failed = True
            continue
        location = client.get_dataset(name).location
        status = "PASS" if location == BQ_LOCATION else "FAIL"
        failed |= status == "FAIL"
        print(f"{status}  {name:<15} location={location}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
