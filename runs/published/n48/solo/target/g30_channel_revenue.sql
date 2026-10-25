-- Teradata session mode: string comparison is case-insensitive and ignores trailing spaces.
CREATE TABLE channel_revenue_30 AS
SELECT cust_id, SUM(amount) AS revenue, COUNT(*) AS order_cnt
FROM orders
WHERE upper(rtrim(channel, ' ')) = upper(rtrim('APP', ' '))
GROUP BY cust_id;