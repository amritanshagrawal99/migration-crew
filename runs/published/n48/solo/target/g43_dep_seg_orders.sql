-- Teradata session mode: string comparison is case-insensitive and ignores trailing spaces.
CREATE TABLE seg_orders_43 AS
SELECT f.cust_id, COUNT(*) AS order_cnt
FROM seg_gold_19 f
INNER JOIN orders o ON f.cust_id = o.cust_id
WHERE upper(rtrim(o.status, ' ')) = upper(rtrim('Pending', ' '))
GROUP BY f.cust_id;