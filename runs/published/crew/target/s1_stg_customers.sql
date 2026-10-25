CREATE OR REPLACE TABLE stg_customers AS
SELECT
    cust_id,
    TRIM(cust_code, ' ') AS cust_code,
    UPPER(TRIM(first_name, ' ')) || ' ' || UPPER(TRIM(last_name, ' ')) AS full_name,
    CASE
        -- Teradata session mode: NOT CASESPECIFIC, trailing pad spaces ignored
        WHEN UPPER(RTRIM(segment, ' ')) = UPPER(RTRIM('gold', ' ')) THEN 'GOLD'
        WHEN UPPER(RTRIM(segment, ' ')) = UPPER(RTRIM('silver', ' ')) THEN 'SILVER'
        ELSE 'STANDARD'
    END AS segment_std,
    COALESCE(credit_limit, 0) AS credit_limit,
    SUBSTRING(email, STRPOS(UPPER(email), '@') + 1) AS email_domain,
    signup_date
FROM customers;