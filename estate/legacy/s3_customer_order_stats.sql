-- OUTPUT: customer_order_stats
-- KEY: cust_id
-- Teradata BTEQ job. Per-customer order statistics.
CREATE MULTISET TABLE customer_order_stats AS (
    SELECT
        cust_id,
        COUNT(*) AS order_cnt,
        SUM(is_shipped) AS shipped_cnt,
        SUM(total_items) AS items_total,
        CAST(SUM(total_items) AS INTEGER) / CAST(COUNT(*) AS INTEGER) AS avg_items_per_order,
        SUM(amount) AS lifetime_value,
        CAST(SUM(amount) AS DECIMAL(14,1)) AS lifetime_value_1dp,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS last_order_date
    FROM stg_orders
    GROUP BY cust_id
) WITH DATA PRIMARY INDEX (cust_id);
