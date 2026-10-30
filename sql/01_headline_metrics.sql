-- One row per bank x fiscal year x headline metric, derived from the clean BRSR table.
-- `better` says which direction is favourable, so ranks and scorecards read the same way for every metric.
CREATE OR REPLACE TABLE `{project}.hrbench_marts.headline_metrics` AS
WITH c AS (
  SELECT * FROM `{project}.hrbench_clean.brsr_clean`
),
direct AS (
  -- metrics reported directly as a %
  SELECT bank, fiscal_year, m.name AS metric, value, m.better, source_file, page, caveat, restated
  FROM c
  JOIN UNNEST([
    STRUCT('turnover_rate_permanent' AS src, 'total' AS g, 'turnover_total' AS name, 'lower' AS better),
    ('turnover_rate_permanent', 'female', 'turnover_female', 'lower'),
    ('turnover_rate_permanent', 'male', 'turnover_male', 'lower'),
    ('training_skill_upgradation_pct', 'total', 'skill_training_pct', 'higher'),
    ('training_health_safety_pct', 'total', 'hs_training_pct', 'higher'),
    ('review_pct', 'total', 'review_pct', 'higher'),
    ('parental_return_to_work_rate', 'female', 'parental_return_female', 'higher'),
    ('parental_retention_rate', 'female', 'parental_retention_female', 'higher'),
    ('parental_retention_rate', 'total', 'parental_retention_total', 'higher'),
    ('female_wages_pct_of_total', 'total', 'female_wages_pct', 'higher'),
    ('wellbeing_spend_pct_revenue', 'total', 'wellbeing_spend_pct_revenue', 'higher')
  ]) AS m
    ON c.metric = m.src AND c.gender = m.g
),
shares AS (
  -- women's share computed from counts: female / total
  SELECT f.bank, f.fiscal_year, m.name AS metric,
         ROUND(100 * SAFE_DIVIDE(f.value, t.value), 2) AS value, 'higher' AS better,
         f.source_file, f.page, f.caveat, f.restated OR t.restated AS restated
  FROM c AS f
  JOIN c AS t
    ON f.bank = t.bank AND f.fiscal_year = t.fiscal_year AND f.metric = t.metric
   AND f.gender = 'female' AND t.gender = 'total'
  JOIN UNNEST([
    STRUCT('headcount_permanent' AS src, 'women_share_permanent' AS name),
    ('board_members', 'women_on_board_pct'),
    ('kmp_members', 'women_in_kmp_pct')
  ]) AS m
    ON f.metric = m.src
)
SELECT bank, fiscal_year, metric, value, '%' AS unit, better, source_file, page, caveat, restated
FROM direct
UNION ALL
SELECT bank, fiscal_year, metric, value, '%', better, source_file, page, caveat, restated
FROM shares;
