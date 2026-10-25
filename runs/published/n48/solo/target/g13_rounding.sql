-- Teradata RoundHalfwayMagUp=FALSE: DECIMAL cast rounds half to even (DuckDB CAST rounds half away from zero).
CREATE TABLE value_1dp_13 AS
SELECT cust_id, CAST(round_even(SUM(amount), 1) AS DECIMAL(14,1)) AS value_1dp
FROM orders
WHERE order_date >= DATE '2026-07-01'
GROUP BY cust_id;