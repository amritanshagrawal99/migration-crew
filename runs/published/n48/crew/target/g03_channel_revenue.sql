-- Teradata session mode: character comparison is NOT CASESPECIFIC and ignores trailing spaces.
CREATE TABLE channel_revenue_03 AS
SELECT
    cust_id,
    SUM(amount) AS revenue,
    COUNT(*) AS order_cnt
FROM orders
WHERE lower(rtrim(channel, ' ')) = lower(rtrim('WEB', ' '))
GROUP BY cust_id;