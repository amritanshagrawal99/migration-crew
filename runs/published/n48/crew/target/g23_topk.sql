CREATE OR REPLACE TABLE top5_23 AS
SELECT cust_id, metric
FROM (
    SELECT cust_id, metric,
           RANK() OVER (ORDER BY metric DESC NULLS LAST) AS rk
    FROM (
        SELECT cust_id, SUM(total_items) AS metric
        FROM orders
        GROUP BY cust_id
    ) g
) r
WHERE rk <= 5;