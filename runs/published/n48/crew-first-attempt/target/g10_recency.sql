CREATE TABLE recency_10 AS
SELECT
    o.cust_id,
    CAST(r.run_date - MAX(o.order_date) AS BIGINT) AS days_since,
    CAST(CASE WHEN r.run_date - MAX(o.order_date) > 60 THEN 1 ELSE 0 END AS INTEGER) AS lapsed
FROM orders AS o
CROSS JOIN etl_control AS r
GROUP BY o.cust_id, r.run_date;