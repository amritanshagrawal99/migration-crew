CREATE TABLE stg_orders AS
SELECT
    order_id,
    cust_id,
    order_date,
    ship_date,
    ship_date - order_date AS ship_lag_days,
    CASE WHEN upper(rtrim(status)) IN ('SHIPPED', 'DELIVERED') THEN 1 ELSE 0 END AS is_shipped,
    CASE
        WHEN upper(rtrim(channel)) = 'WEB' THEN 'web'
        WHEN upper(rtrim(channel)) = 'APP' THEN 'app'
        ELSE 'store'
    END AS channel_std,
    total_items,
    amount
FROM orders;
