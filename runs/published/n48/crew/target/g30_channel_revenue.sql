-- Teradata session mode: character comparison is NOT CASESPECIFIC and ignores trailing spaces.
CREATE OR REPLACE TABLE channel_revenue_30 AS
SELECT
    cust_id,
    SUM(amount) AS revenue,
    COUNT(*) AS order_cnt
FROM orders
WHERE lower(rtrim(channel, ' ')) = lower(rtrim('APP', ' '))
GROUP BY cust_id;