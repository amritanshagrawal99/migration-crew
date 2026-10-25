-- Teradata session mode: string comparisons are NOT CASESPECIFIC and ignore trailing pad spaces.
CREATE TABLE stg_orders AS
SELECT
    order_id,
    cust_id,
    order_date,
    ship_date,
    CAST(ship_date - order_date AS INTEGER) AS ship_lag_days,
    CASE WHEN upper(rtrim(status, ' ')) IN (upper('shipped'), upper('delivered')) THEN 1 ELSE 0 END AS is_shipped,
    CASE
        WHEN upper(rtrim(channel, ' ')) = upper('WEB') THEN 'web'
        WHEN upper(rtrim(channel, ' ')) = upper('APP') THEN 'app'
        ELSE 'store'
    END AS channel_std,
    total_items,
    amount
FROM orders;