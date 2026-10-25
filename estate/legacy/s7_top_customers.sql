-- OUTPUT: top_customers
-- KEY: cust_id
-- Teradata BTEQ job. The ten most frequent customers, keeping ties at the boundary.
CREATE MULTISET TABLE top_customers AS (
    SELECT TOP 10 WITH TIES
        s.cust_id,
        c.full_name,
        c.segment_std,
        s.order_cnt,
        s.lifetime_value
    FROM customer_order_stats s
    INNER JOIN stg_customers c
        ON s.cust_id = c.cust_id
    ORDER BY s.order_cnt DESC
) WITH DATA PRIMARY INDEX (cust_id);
