-- Teradata INTEGER / INTEGER truncates.
CREATE TABLE customer_order_stats AS
SELECT
    cust_id,
    count(*) AS order_cnt,
    sum(is_shipped) AS shipped_cnt,
    sum(total_items) AS items_total,
    CAST(sum(total_items) AS BIGINT) // CAST(count(*) AS BIGINT) AS avg_items_per_order,
    sum(amount) AS lifetime_value,
    -- RoundHalfwayMagUp=FALSE: DECIMAL rounding is half-to-even. Done in exact integer arithmetic on the cents:
    -- DuckDB 1.5's round_even() on DECIMAL goes through a double (1164.65 -> 1164.7), 2.0's is exact.
    CAST(
        (CAST(sum(amount) * 100 AS BIGINT) // 10
         + CASE
               WHEN CAST(sum(amount) * 100 AS BIGINT) % 10 > 5 THEN 1
               WHEN CAST(sum(amount) * 100 AS BIGINT) % 10 = 5 THEN (CAST(sum(amount) * 100 AS BIGINT) // 10) % 2
               ELSE 0
           END) AS DECIMAL(14, 0)) / 10 AS lifetime_value_1dp,
    min(order_date) AS first_order_date,
    max(order_date) AS last_order_date
FROM stg_orders
GROUP BY cust_id;
