-- Teradata session mode: character comparison is NOT CASESPECIFIC and ignores trailing spaces.
CREATE OR REPLACE TABLE channel_revenue_26 AS
SELECT
    cust_id,
    SUM(amount) AS revenue,
    COUNT(*) AS order_cnt
FROM orders
WHERE lower(rtrim(channel, ' ')) = lower(rtrim('App', ' '))
GROUP BY cust_id;