-- TOP 10 WITH TIES ... ORDER BY value_1dp DESC  ->  RANK() <= 10.
-- Teradata sorts NULL lowest, so NULLs go last in DESC (a NULL value_1dp never takes a top slot).
-- Ranking is on the already-rounded DECIMAL(14,1) from value_1dp_05, so ties follow the half-even rounded value.
CREATE OR REPLACE TABLE top_value_46 AS
SELECT cust_id, value_1dp
FROM (
    SELECT cust_id, value_1dp,
           RANK() OVER (ORDER BY value_1dp DESC NULLS LAST) AS rk
    FROM value_1dp_05
) r
WHERE rk <= 10;