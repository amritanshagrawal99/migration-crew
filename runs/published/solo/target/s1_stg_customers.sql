-- Teradata session mode: character comparisons are NOT CASESPECIFIC and ignore trailing spaces.
-- Emulated as LOWER(RTRIM(x)) = LOWER(RTRIM(y)).
CREATE TABLE stg_customers AS
SELECT
    cust_id,
    TRIM(cust_code) AS cust_code,
    UPPER(TRIM(first_name)) || ' ' || UPPER(TRIM(last_name)) AS full_name,
    CASE
        WHEN LOWER(RTRIM(segment)) = LOWER(RTRIM('gold')) THEN 'GOLD'
        WHEN LOWER(RTRIM(segment)) = LOWER(RTRIM('silver')) THEN 'SILVER'
        ELSE 'STANDARD'
    END AS segment_std,
    COALESCE(credit_limit, 0) AS credit_limit,
    SUBSTRING(email, STRPOS(email, '@') + 1) AS email_domain,
    signup_date
FROM customers;