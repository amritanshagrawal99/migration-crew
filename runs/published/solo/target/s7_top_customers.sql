-- Trap: TOP n WITH TIES has no direct DuckDB equivalent; emulated with RANK() <= n over the same ORDER BY
-- (Teradata sorts NULLs first; DESC => NULLS LAST, stated explicitly).
CREATE TABLE top_customers AS
SELECT cust_id, full_name, segment_std, order_cnt, lifetime_value
FROM (
    SELECT
        s.cust_id,
        c.full_name,
        c.segment_std,
        s.order_cnt,
        s.lifetime_value,
        RANK() OVER (ORDER BY s.order_cnt DESC NULLS LAST) AS rnk
    FROM customer_order_stats s
    INNER JOIN stg_customers c
        ON s.cust_id = c.cust_id
) t
WHERE rnk <= 10;