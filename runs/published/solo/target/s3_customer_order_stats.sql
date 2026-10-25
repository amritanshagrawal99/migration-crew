-- Traps:
--  * Teradata INTEGER / INTEGER truncates toward zero; DuckDB '/' returns a DOUBLE. Emulated sign-aware.
--  * CAST to DECIMAL(14,1): Teradata with RoundHalfwayMagUp=FALSE rounds half to even (banker's);
--    DuckDB casts round half away from zero. Emulated exactly with decimal arithmetic.
CREATE TABLE customer_order_stats AS
WITH agg AS (
    SELECT
        cust_id,
        COUNT(*) AS order_cnt,
        SUM(is_shipped) AS shipped_cnt,
        SUM(total_items) AS items_total,
        CAST(SUM(total_items) AS INTEGER) AS num_i,
        CAST(COUNT(*) AS INTEGER) AS den_i,
        SUM(amount) AS lifetime_value,
        SUM(amount) * 10 AS lv_x10,
        FLOOR(SUM(amount) * 10) AS lv_x10_floor,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS last_order_date
    FROM stg_orders
    GROUP BY cust_id
)
SELECT
    cust_id,
    order_cnt,
    shipped_cnt,
    items_total,
    CAST(SIGN(num_i) * SIGN(den_i) * (ABS(num_i) // ABS(den_i)) AS INTEGER) AS avg_items_per_order,
    lifetime_value,
    CAST(
        (CASE
            WHEN lv_x10 - lv_x10_floor > 0.5 THEN lv_x10_floor + 1
            WHEN lv_x10 - lv_x10_floor < 0.5 THEN lv_x10_floor
            WHEN lv_x10_floor % 2 = 0 THEN lv_x10_floor
            ELSE lv_x10_floor + 1
        END) / 10 AS DECIMAL(14,1)) AS lifetime_value_1dp,
    first_order_date,
    last_order_date
FROM agg;