-- Join keys (cust_id) are INTEGER in all inputs: no text-comparison semantics apply.
-- Teradata DATE - DATE yields INTEGER days; DuckDB yields BIGINT days, cast to INTEGER for type parity.
-- NULL last_order_date or run_date -> NULL difference -> both WHEN tests unknown -> ELSE 'LOW' (as legacy).
-- Run date is read from etl_control (cross join, as legacy).
CREATE TABLE churn_flags AS
SELECT
    s.cust_id,
    c.segment_std,
    CAST(r.run_date - s.last_order_date AS INTEGER) AS days_since_last_order,
    CASE
        WHEN r.run_date - s.last_order_date > 90 THEN 'HIGH'
        WHEN r.run_date - s.last_order_date > 30 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS churn_risk,
    CASE WHEN f.ship_date IS NULL THEN 1 ELSE 0 END AS first_order_unshipped
FROM customer_order_stats AS s
INNER JOIN stg_customers AS c
    ON s.cust_id = c.cust_id
INNER JOIN first_fulfilment AS f
    ON s.cust_id = f.cust_id
CROSS JOIN etl_control AS r;