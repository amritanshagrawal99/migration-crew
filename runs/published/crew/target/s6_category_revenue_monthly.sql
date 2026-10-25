-- Teradata session mode: GROUP BY on character columns is NOT CASESPECIFIC and ignores
-- trailing spaces, so categories differing only in case/trailing blanks collapse into one
-- group. Group on the normalised value and output one original spelling (MIN over originals).
-- yyyymm: EXTRACT(YEAR)*100+EXTRACT(MONTH) -> integer (BIGINT in legacy output).
-- revenue: SUM of DECIMAL(.,2) -> DECIMAL(38,2).
CREATE TABLE category_revenue_monthly AS
SELECT
    CAST(EXTRACT(YEAR FROM o.order_date) * 100 + EXTRACT(MONTH FROM o.order_date) AS BIGINT) AS yyyymm,
    MIN(e.category) AS category,
    CAST(SUM(e.line_amount) AS DECIMAL(38,2)) AS revenue,
    COUNT(*) AS line_cnt
FROM order_lines_enriched AS e
INNER JOIN stg_orders AS o
    ON e.order_id = o.order_id
WHERE o.is_shipped = 1
GROUP BY
    CAST(EXTRACT(YEAR FROM o.order_date) * 100 + EXTRACT(MONTH FROM o.order_date) AS BIGINT),
    upper(rtrim(e.category, ' '));
