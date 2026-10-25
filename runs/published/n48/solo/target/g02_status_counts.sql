-- Teradata session mode: IN-list comparison is case-insensitive and ignores trailing spaces.
CREATE TABLE status_counts_02 AS
SELECT cust_id, COUNT(*) AS order_cnt,
       SUM(CASE WHEN upper(rtrim(status, ' ')) IN (upper(rtrim('pending', ' ')), upper(rtrim('Shipped', ' '))) THEN 1 ELSE 0 END) AS match_cnt
FROM orders
GROUP BY cust_id;