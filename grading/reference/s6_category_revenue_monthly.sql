CREATE TABLE category_revenue_monthly AS
SELECT
    extract(year FROM o.order_date) * 100 + extract(month FROM o.order_date) AS yyyymm,
    e.category,
    sum(e.line_amount) AS revenue,
    count(*) AS line_cnt
FROM order_lines_enriched e
INNER JOIN stg_orders o ON e.order_id = o.order_id
WHERE o.is_shipped = 1
GROUP BY 1, 2;
