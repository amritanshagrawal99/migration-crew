CREATE OR REPLACE TABLE seg_gold_14 AS
SELECT cust_id, TRIM(cust_code, ' ') AS cust_code, signup_date
FROM customers
WHERE lower(rtrim(segment, ' ')) = lower(rtrim('gold', ' '));