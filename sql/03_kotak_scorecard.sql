-- Kotak vs peer median on every headline metric: latest year, first year, and whether the gap is widening.
CREATE OR REPLACE TABLE `{project}.hrbench_marts.kotak_scorecard` AS
WITH k AS (
  SELECT * FROM `{project}.hrbench_marts.benchmark` WHERE bank = 'KOTAK'
),
latest AS (
  SELECT * FROM k
  QUALIFY ROW_NUMBER() OVER (PARTITION BY metric ORDER BY fiscal_year DESC) = 1
),
first_year AS (
  SELECT * FROM k
  QUALIFY ROW_NUMBER() OVER (PARTITION BY metric ORDER BY fiscal_year) = 1
)
SELECT
  l.metric,
  l.better,
  l.fiscal_year AS latest_year,
  l.value AS kotak_value,
  l.peer_median,
  l.gap_to_peer_median,
  l.rank_in_year,
  l.n_banks,
  CASE
    WHEN l.advantage_vs_peer_median > 0 THEN 'ahead of peers'
    WHEN l.advantage_vs_peer_median < 0 THEN 'behind peers'
    ELSE 'at peer median'
  END AS position,
  f.fiscal_year AS first_year,
  f.advantage_vs_peer_median AS first_advantage,
  l.advantage_vs_peer_median AS latest_advantage,
  CASE
    WHEN f.fiscal_year = l.fiscal_year THEN 'one year only'
    WHEN l.advantage_vs_peer_median > f.advantage_vs_peer_median THEN 'improving vs peers'
    WHEN l.advantage_vs_peer_median < f.advantage_vs_peer_median THEN 'worsening vs peers'
    ELSE 'unchanged'
  END AS trend,
  l.source_file,
  l.page,
  l.caveat
FROM latest AS l
JOIN first_year AS f USING (metric);
