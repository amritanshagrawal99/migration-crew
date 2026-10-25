-- TOP n WITH TIES -> RANK() <= n. Teradata sorts NULLs low (last in DESC), made explicit.
CREATE TABLE top5_23 AS
SELECT cust_id, metric FROM (
    SELECT cust_id, SUM(total_items) AS metric,
           RANK() OVER (ORDER BY SUM(total_items) DESC NULLS LAST) AS rk
    FROM orders
    GROUP BY cust_id
) t
WHERE rk <= 5;