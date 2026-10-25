CREATE TABLE items_ratio_08 AS
SELECT
    cust_id,
    -- Teradata INTEGER / INTEGER truncates toward zero; DuckDB's // on integers truncates toward zero
    CAST(CAST(SUM(total_items) AS INTEGER) // CAST(COUNT(*) AS INTEGER) AS BIGINT) AS items_per_order
FROM orders
GROUP BY cust_id;