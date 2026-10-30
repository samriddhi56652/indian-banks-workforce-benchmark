-- Each bank vs the peer group, per metric and year.
-- Peer group = the 5 banks other than Kotak; Kotak is excluded from its own benchmark.
-- RANK (not DENSE_RANK): two banks tied at 2nd are both 2, and the next is 4th,
-- so a rank always means "how many banks did better, plus one".
CREATE OR REPLACE TABLE `{project}.hrbench_marts.benchmark` AS
WITH m AS (
  SELECT * FROM `{project}.hrbench_marts.headline_metrics`
  WHERE value IS NOT NULL
),
peer AS (
  SELECT DISTINCT
    metric, fiscal_year,
    PERCENTILE_CONT(value, 0.5) OVER (PARTITION BY metric, fiscal_year) AS peer_median,
    AVG(value) OVER (PARTITION BY metric, fiscal_year) AS peer_avg,
    COUNT(*) OVER (PARTITION BY metric, fiscal_year) AS n_peers
  FROM m
  WHERE bank != 'KOTAK'
),
ranked AS (
  SELECT
    m.*,
    RANK() OVER (
      PARTITION BY m.metric, m.fiscal_year
      ORDER BY IF(m.better = 'higher', -m.value, m.value)
    ) AS rank_in_year,
    COUNT(*) OVER (PARTITION BY m.metric, m.fiscal_year) AS n_banks,
    p.peer_median, p.peer_avg, p.n_peers,
    m.value - p.peer_median AS gap_to_peer_median,
    m.value - p.peer_avg AS gap_to_peer_avg
  FROM m
  JOIN peer AS p USING (metric, fiscal_year)
)
SELECT
  *,
  value - LAG(value) OVER (PARTITION BY bank, metric ORDER BY fiscal_year) AS yoy_change,
  gap_to_peer_median
    - LAG(gap_to_peer_median) OVER (PARTITION BY bank, metric ORDER BY fiscal_year) AS gap_change,
  -- positive = better than the peer median, whichever direction the metric runs
  IF(better = 'higher', 1, -1) * (value - peer_median) AS advantage_vs_peer_median
FROM ranked;
