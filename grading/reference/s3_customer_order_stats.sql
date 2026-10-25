-- Teradata INTEGER / INTEGER truncates.
CREATE TABLE customer_order_stats AS
SELECT
    cust_id,
    count(*) AS order_cnt,
    sum(is_shipped) AS shipped_cnt,
    sum(total_items) AS items_total,
    CAST(sum(total_items) AS BIGINT) // CAST(count(*) AS BIGINT) AS avg_items_per_order,
    sum(amount) AS lifetime_value,
    -- RoundHalfwayMagUp=FALSE: DECIMAL rounding is half-to-even
    CAST(round_even(sum(amount), 1) AS DECIMAL(14,1)) AS lifetime_value_1dp,
    min(order_date) AS first_order_date,
    max(order_date) AS last_order_date
FROM stg_orders
GROUP BY cust_id;
