-- OUTPUT: category_revenue_monthly
-- KEY: yyyymm, category
-- Teradata BTEQ job. Shipped revenue per category and month.
CREATE MULTISET TABLE category_revenue_monthly AS (
    SELECT
        EXTRACT(YEAR FROM o.order_date) * 100 + EXTRACT(MONTH FROM o.order_date) AS yyyymm,
        e.category,
        SUM(e.line_amount) AS revenue,
        COUNT(*) AS line_cnt
    FROM order_lines_enriched e
    INNER JOIN stg_orders o
        ON e.order_id = o.order_id
    WHERE o.is_shipped = 1
    GROUP BY 1, 2
) WITH DATA PRIMARY INDEX (yyyymm, category);
