-- TOP n WITH TIES -> RANK() <= n; Teradata NULLs sort last in DESC.
CREATE TABLE top_value_46 AS
SELECT cust_id, value_1dp FROM (
    SELECT cust_id, value_1dp, RANK() OVER (ORDER BY value_1dp DESC NULLS LAST) AS rk
    FROM value_1dp_05
) t
WHERE rk <= 10;