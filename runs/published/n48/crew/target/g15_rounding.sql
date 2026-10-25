-- Teradata CAST to DECIMAL(14,1) rounds half-to-even (RoundHalfwayMagUp=FALSE).
-- Exact integer arithmetic on the scale-2 sum (DuckDB CAST rounds half away from zero; round_even goes via double).
CREATE TABLE value_1dp_15 AS
WITH s AS (
    SELECT cust_id, CAST(SUM(amount) * 100 AS HUGEINT) AS c   -- exact: SUM(DECIMAL(12,2)) has scale 2
    FROM orders
    WHERE order_date >= DATE '2026-03-01'
    GROUP BY cust_id
), q AS (
    SELECT cust_id, sign(c) AS sg, abs(c) // 10 AS qt, abs(c) % 10 AS rm
    FROM s
)
SELECT cust_id,
       CAST(CAST(sg * (qt + CASE WHEN rm > 5 OR (rm = 5 AND qt % 2 = 1) THEN 1 ELSE 0 END) AS DECIMAL(37,0)) * CAST(0.1 AS DECIMAL(2,1))
            AS DECIMAL(14,1)) AS value_1dp
FROM q;