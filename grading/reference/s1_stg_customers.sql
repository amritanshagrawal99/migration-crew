-- Reference (hidden). Teradata session-mode string comparison = case- and trailing-space-insensitive.
CREATE TABLE stg_customers AS
SELECT
    cust_id,
    trim(cust_code) AS cust_code,
    upper(trim(first_name)) || ' ' || upper(trim(last_name)) AS full_name,
    CASE
        WHEN upper(rtrim(segment)) = 'GOLD' THEN 'GOLD'
        WHEN upper(rtrim(segment)) = 'SILVER' THEN 'SILVER'
        ELSE 'STANDARD'
    END AS segment_std,
    coalesce(credit_limit, 0) AS credit_limit,
    substr(email, strpos(email, '@') + 1) AS email_domain,
    signup_date
FROM customers;
