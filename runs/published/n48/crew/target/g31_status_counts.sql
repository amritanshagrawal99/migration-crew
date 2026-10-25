CREATE OR REPLACE TABLE status_counts_31 AS
SELECT
    cust_id,
    COUNT(*) AS order_cnt,
    SUM(CASE WHEN lower(rtrim(status, ' ')) IN (lower(rtrim('delivered', ' '))) THEN 1 ELSE 0 END) AS match_cnt
FROM orders
GROUP BY cust_id;