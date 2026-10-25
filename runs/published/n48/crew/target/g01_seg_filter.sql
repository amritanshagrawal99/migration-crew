CREATE TABLE seg_silver_01 AS
SELECT cust_id, TRIM(cust_code, ' ') AS cust_code, signup_date
FROM customers
WHERE lower(rtrim(segment, ' ')) = lower(rtrim('silver', ' '));