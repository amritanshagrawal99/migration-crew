-- Teradata INTEGER / INTEGER truncates toward zero; DuckDB '/' returns DOUBLE, '//' truncates.
CREATE TABLE items_ratio_08 AS
SELECT cust_id, CAST(SUM(total_items) AS INTEGER) // CAST(COUNT(*) AS INTEGER) AS items_per_order
FROM orders
GROUP BY cust_id;