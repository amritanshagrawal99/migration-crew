CREATE OR REPLACE TABLE seg_orders_41 AS
SELECT f.cust_id, COUNT(*) AS order_cnt
FROM seg_gold_11 f
INNER JOIN orders o ON f.cust_id = o.cust_id
WHERE lower(rtrim(o.status, ' ')) = lower(rtrim('Delivered', ' '))
GROUP BY f.cust_id;