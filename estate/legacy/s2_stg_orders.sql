-- OUTPUT: stg_orders
-- KEY: order_id
-- Teradata BTEQ job (session mode). Order staging with fulfilment flags.
CREATE MULTISET TABLE stg_orders AS (
    SELECT
        order_id,
        cust_id,
        order_date,
        ship_date,
        ship_date - order_date AS ship_lag_days,
        CASE WHEN status IN ('shipped', 'delivered') THEN 1 ELSE 0 END AS is_shipped,
        CASE
            WHEN channel = 'WEB' THEN 'web'
            WHEN channel = 'APP' THEN 'app'
            ELSE 'store'
        END AS channel_std,
        total_items,
        amount
    FROM orders
) WITH DATA PRIMARY INDEX (order_id);
