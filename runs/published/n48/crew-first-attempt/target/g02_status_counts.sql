CREATE TABLE status_counts_02 AS
SELECT
    cust_id,
    COUNT(*) AS order_cnt,
    SUM(CASE WHEN lower(rtrim(status)) IN (lower(rtrim('pending')), lower(rtrim('Shipped'))) THEN 1 ELSE 0 END) AS match_cnt
FROM orders
GROUP BY cust_id;