-- cust_id is INTEGER: no text-comparison semantics apply to the GROUP BY.
-- Teradata integer/integer division truncates toward zero; DuckDB '/' returns DOUBLE, so divide exact integers
-- with truncation toward zero made explicit (sign handled separately).
-- CAST(... AS DECIMAL(14,1)) rounds half-to-even on legacy (RoundHalfwayMagUp=FALSE); DuckDB rounds half away
-- from zero, so the rounding is done explicitly on the exact scaled integer value (no floating point).
CREATE TABLE customer_order_stats AS
WITH agg AS (
    SELECT
        cust_id,
        COUNT(*) AS order_cnt,
        SUM(is_shipped) AS shipped_cnt,
        SUM(total_items) AS items_total,
        CAST(SUM(total_items) AS INTEGER) AS items_int,
        CAST(COUNT(*) AS INTEGER) AS cnt_int,
        SUM(amount) AS lifetime_value,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS last_order_date
    FROM stg_orders
    GROUP BY cust_id
),
scaled AS (
    SELECT *,
        -- exact value in units of 10^-2 (amount scale is 2), split into magnitude and sign
        abs(CAST(lifetime_value * 100 AS HUGEINT)) AS lv_abs,
        CAST(sign(lifetime_value) AS HUGEINT) AS lv_sign
    FROM agg
)
SELECT
    cust_id,
    order_cnt,
    shipped_cnt,
    items_total,
    CAST(CASE WHEN (items_int < 0) = (cnt_int < 0)
              THEN abs(items_int) // abs(cnt_int)
              ELSE -(abs(items_int) // abs(cnt_int)) END AS BIGINT) AS avg_items_per_order,
    lifetime_value,
    CAST(
        CAST(lv_sign * (
                (lv_abs // 10)
                + CASE WHEN lv_abs % 10 > 5 OR (lv_abs % 10 = 5 AND (lv_abs // 10) % 2 = 1) THEN 1 ELSE 0 END
             ) AS DECIMAL(37,0)) * CAST(0.1 AS DECIMAL(2,1))
        AS DECIMAL(14,1)) AS lifetime_value_1dp,
    first_order_date,
    last_order_date
FROM scaled;