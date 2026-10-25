-- TOP n WITH TIES -> RANK() <= n. Teradata sorts NULLs low (last in DESC), made explicit.
CREATE TABLE top10_22 AS
SELECT cust_id, metric FROM (
    SELECT cust_id, COUNT(*) AS metric,
           RANK() OVER (ORDER BY COUNT(*) DESC NULLS LAST) AS rk
    FROM orders
    GROUP BY cust_id
) t
WHERE rk <= 10;