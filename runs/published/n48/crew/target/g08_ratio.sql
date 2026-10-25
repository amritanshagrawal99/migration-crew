CREATE TABLE items_ratio_08 AS
WITH g AS (
    SELECT cust_id,
           CAST(SUM(total_items) AS INTEGER) AS s,
           CAST(COUNT(*) AS INTEGER) AS n
    FROM orders
    GROUP BY cust_id
)
SELECT cust_id,
       -- Teradata INTEGER / INTEGER truncates toward zero; DuckDB // floors for negatives
       CAST(CASE WHEN (s < 0) <> (n < 0) THEN -(abs(s) // abs(n))
                 ELSE abs(s) // abs(n) END AS BIGINT) AS items_per_order
FROM g;