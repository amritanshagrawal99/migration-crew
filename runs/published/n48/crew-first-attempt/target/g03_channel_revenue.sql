CREATE TABLE channel_revenue_03 AS
SELECT
    cust_id,
    CAST(SUM(amount) AS DECIMAL(38,2)) AS revenue,
    CAST(COUNT(*) AS BIGINT) AS order_cnt
FROM orders
WHERE lower(rtrim(channel)) = lower(rtrim('WEB'))
GROUP BY cust_id;