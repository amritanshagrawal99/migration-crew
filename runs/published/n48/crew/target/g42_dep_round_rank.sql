CREATE OR REPLACE TABLE top_value_42 AS
SELECT cust_id, value_1dp
FROM (
    SELECT cust_id, value_1dp,
           RANK() OVER (ORDER BY value_1dp DESC NULLS LAST) AS rk
    FROM value_1dp_20
) r
WHERE rk <= 10;