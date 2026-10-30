# Indian Banks Workforce Benchmarking Study

**Question:** How does Kotak Mahindra Bank compare with peer private-sector banks on attrition, diversity, learning, performance reviews and employee wellbeing, and where should HR leadership focus?

**Scope:** Kotak Mahindra Bank vs HDFC, ICICI, Axis, IndusInd and YES Bank, FY2023-24 to FY2025-26.
**Data:** each bank's Business Responsibility and Sustainability Report (BRSR), the workforce disclosure SEBI requires from India's top listed companies. Public documents only.

## Key findings (FY2025-26)

| | Kotak | Peer median* | Rank of 6 |
|---|---|---|---|
| Permanent-employee turnover (lower is better) | **32.5%** | 23.1% | 4 |
| Women still employed 12 months after returning from parental leave | **64.2%** | 77.95% | 6 |
| Employees trained on skill upgradation | **90.9%** | 99.4% | 5 |
| Employees receiving performance & career reviews | **87.3%** | 92.0% | 4 |
| Women, % of permanent employees | **27.35%** | 26.61% | 3 |

\* Median of the five peers; Kotak excluded.

1. **Attrition is falling but remains the largest gap.** Kotak's turnover fell from 39.6% (FY2023-24) to 32.5%, but peers improved too: the gap to the peer median narrowed only from 10.8 to 9.4 percentage points.
2. **Women's retention after parental leave is the lowest of the six banks**, and the gap to the peer median widened from 9.2 to 13.75 points. Return-to-work is about 99% at every bank, so the loss happens in the year after return.
3. **Learning and review coverage trail peers.** Part of the training gap may be definitional: Kotak reports training on all employees including fixed-term staff, while peers report permanent employees only.

Exploratory only: across 17 bank-years, banks with higher skill-training coverage report lower turnover (Pearson r = −0.69). With six banks and repeated years per bank this is a pattern to discuss, not evidence of cause.

Every figure above comes from `data/marts/` and traces to a report and PDF page (`source_file`, `page` columns).

## Dashboard

`dashboard/index.html` is a self-contained page (no internet needed). Download it and open it in a browser: summary, attrition, diversity, learning & performance, employee experience, a Kotak scorecard, and method & caveats. Hover any mark for its source report and page.

## Method

```
18 BRSR PDFs ──► locate_tables.py ──► extract_brsr.py ──► verify_extraction.py
                 (find each table,     (23 metrics,         (re-find every value on its
                  confirm the year)     one long table)      cited page; eye-check sheet)
                                                │
                                         build_clean.py  (one value per bank-year;
                                                │         restatements and caveats flagged)
                                                ▼
                     BigQuery: hrbench_raw ─► hrbench_clean ─► hrbench_marts
                                                                  │  sql/01–04: RANK, PERCENTILE_CONT,
                                                                  │  LAG, CORR; peer median and gaps
                                                                  ▼
                                               data/marts/*.csv ─► build_dashboard.py ─► dashboard/index.html
```

- **1,297 values** extracted from 18 reports (1,248 parsed automatically, 49 entered by hand from the PDF where a table could not be parsed safely). Each row keeps the report, PDF page and the text exactly as printed.
- **Checks:** arithmetic (male + female = total; % within 0–100), every value re-found on its cited page with a second PDF library, ranks 1..n, peer median recomputed in pandas equals BigQuery, row counts equal across CSV → pandas → BigQuery.
- **Restatements:** where a year appears in two reports, the latest report is used and the change is flagged (19 values). The largest: IndusInd changed its turnover method in its FY2025-26 report and restated FY2023-24 from 37% to 45.3%.

## Honesty rules

- Data is what banks self-report in their BRSRs. Definitions differ between banks; non-comparable values are flagged, not hidden. Only Kotak states its turnover formula.
- Six banks is a small sample: the peer median is the 3rd of 5 values, and correlations are exploratory with no causal claims.
- Public disclosures only; no internal Kotak data; no bank logos. Kotak is benchmarked by name because its filings are public.
- "Not disclosed" is reported as missing, never filled with estimates.

## Reproduce

Requires Python 3.14, a Google Cloud project with BigQuery, and Application Default Credentials (`gcloud auth application-default login`). Commands for Windows cmd:

```
py -3.14 -m venv %USERPROFILE%\.venvs\bank-benchmark
%USERPROFILE%\.venvs\bank-benchmark\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your project ID, download the 18 reports listed in `data/SOURCES.md` into `data\raw\brsr\`, then:

```
python src\setup_bq.py
python src\locate_tables.py
python src\extract_brsr.py
python src\verify_extraction.py
python src\build_clean.py
python src\load_bq.py
python src\run_marts.py
python src\build_dashboard.py
```

## Repository layout

| Path | Contents |
|---|---|
| `src/` | Python pipeline (scripts above) |
| `sql/` | BigQuery mart definitions |
| `data/SOURCES.md` | Every report: URL, download date, size, pages of the employee tables |
| `data/page_index.csv` | Page of each table in each report |
| `data/raw/` | Extracted values (`brsr_extracted.csv`), hand-entered values, spot-check sheet; PDFs are not committed |
| `data/clean/` | One value per bank × year × metric × gender, with restatement flags and caveats |
| `data/marts/` | Benchmark outputs used by the dashboard |
| `dashboard/` | HTML dashboard and its template |
