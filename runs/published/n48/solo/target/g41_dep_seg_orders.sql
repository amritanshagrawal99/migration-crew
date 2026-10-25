-- Teradata session mode: string comparison is case-insensitive and ignores trailing spaces.
CREATE TABLE seg_orders_41 AS
SELECT f.cust_id, COUNT(*) AS order_cnt
FROM seg_gold_11 f
INNER JOIN orders o ON f.cust_id = o.cust_id
WHERE upper(rtrim(o.status, ' ')) = upper(rtrim('Delivered', ' '))
GROUP BY f.cust_id;