CREATE OR REPLACE TABLE seg_orders_33 AS
SELECT f.cust_id, COUNT(*) AS order_cnt
FROM seg_silver_17 f
INNER JOIN orders o ON f.cust_id = o.cust_id
WHERE lower(rtrim(o.status, ' ')) = lower(rtrim('DELIVERED', ' '))
GROUP BY f.cust_id;