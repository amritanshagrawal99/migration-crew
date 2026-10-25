-- Teradata session mode: character comparisons are case-insensitive and ignore trailing spaces.
CREATE TABLE stg_orders AS
SELECT
    order_id,
    cust_id,
    order_date,
    ship_date,
    ship_date - order_date AS ship_lag_days,
    CASE WHEN LOWER(RTRIM(status)) IN (LOWER(RTRIM('shipped')), LOWER(RTRIM('delivered'))) THEN 1 ELSE 0 END AS is_shipped,
    CASE
        WHEN LOWER(RTRIM(channel)) = LOWER(RTRIM('WEB')) THEN 'web'
        WHEN LOWER(RTRIM(channel)) = LOWER(RTRIM('APP')) THEN 'app'
        ELSE 'store'
    END AS channel_std,
    total_items,
    amount
FROM orders;