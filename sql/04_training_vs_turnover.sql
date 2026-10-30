-- EXPLORATORY ONLY (Q6): skill-training coverage vs turnover, one point per bank-year.
-- 6 banks x up to 3 years; points from the same bank are not independent. A pattern to discuss, not a finding.
CREATE OR REPLACE TABLE `{project}.hrbench_marts.training_vs_turnover` AS
WITH pairs AS (
  SELECT
    t.bank, t.fiscal_year,
    s.value AS skill_training_pct,
    t.value AS turnover_total
  FROM `{project}.hrbench_marts.headline_metrics` AS t
  JOIN `{project}.hrbench_marts.headline_metrics` AS s
    ON t.bank = s.bank AND t.fiscal_year = s.fiscal_year
  WHERE t.metric = 'turnover_total' AND s.metric = 'skill_training_pct'
    AND t.value IS NOT NULL AND s.value IS NOT NULL
)
SELECT
  *,
  CORR(skill_training_pct, turnover_total) OVER () AS pearson_r_all_points,
  COUNT(*) OVER () AS n_points,
  'exploratory: small sample, not causal' AS label
FROM pairs;
