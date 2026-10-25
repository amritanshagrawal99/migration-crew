CREATE TABLE churn_flags AS
SELECT
    s.cust_id,
    c.segment_std,
    r.run_date - s.last_order_date AS days_since_last_order,
    CASE
        WHEN r.run_date - s.last_order_date > 90 THEN 'HIGH'
        WHEN r.run_date - s.last_order_date > 30 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS churn_risk,
    CASE WHEN f.ship_date IS NULL THEN 1 ELSE 0 END AS first_order_unshipped
FROM customer_order_stats s
INNER JOIN stg_customers c ON s.cust_id = c.cust_id
INNER JOIN first_fulfilment f ON s.cust_id = f.cust_id
CROSS JOIN etl_control r;
