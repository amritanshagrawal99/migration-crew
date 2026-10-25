-- Teradata session mode: string comparison is case-insensitive (NOT CASESPECIFIC) and ignores trailing spaces.
CREATE TABLE seg_silver_01 AS
SELECT cust_id, TRIM(cust_code) AS cust_code, signup_date
FROM customers
WHERE upper(rtrim(segment, ' ')) = upper(rtrim('silver', ' '));