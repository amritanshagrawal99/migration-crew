-- Teradata DATE - DATE yields integer days; DuckDB DATE - DATE also yields integer days.
CREATE TABLE recency_10 AS
SELECT o.cust_id, CAST(r.run_date - MAX(o.order_date) AS INTEGER) AS days_since,
       CASE WHEN r.run_date - MAX(o.order_date) > 60 THEN 1 ELSE 0 END AS lapsed
FROM orders o CROSS JOIN etl_control r
GROUP BY o.cust_id, r.run_date;