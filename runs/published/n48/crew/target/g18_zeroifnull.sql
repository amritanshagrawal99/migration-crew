CREATE TABLE credit_band_18 AS
SELECT
    cust_id,
    CAST(COALESCE(credit_limit, 0) AS DECIMAL(12,2)) AS credit_limit,
    CASE WHEN COALESCE(credit_limit, 0) > 20000 THEN 'HIGH' ELSE 'LOW' END AS band
FROM customers;