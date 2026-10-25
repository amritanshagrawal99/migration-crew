-- Trap: Teradata session mode groups character values case-insensitively and ignoring trailing spaces,
-- so the GROUP BY uses LOWER(RTRIM(category)). Teradata returns an arbitrary member spelling of each
-- group; MIN(category) is used as the deterministic representative.
CREATE TABLE category_revenue_monthly AS
SELECT
    EXTRACT(YEAR FROM o.order_date) * 100 + EXTRACT(MONTH FROM o.order_date) AS yyyymm,
    MIN(e.category) AS category,
    SUM(e.line_amount) AS revenue,
    COUNT(*) AS line_cnt
FROM order_lines_enriched e
INNER JOIN stg_orders o
    ON e.order_id = o.order_id
WHERE o.is_shipped = 1
GROUP BY EXTRACT(YEAR FROM o.order_date) * 100 + EXTRACT(MONTH FROM o.order_date), LOWER(RTRIM(e.category));