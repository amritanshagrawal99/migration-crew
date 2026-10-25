-- OUTPUT: stg_customers
-- KEY: cust_id
-- Teradata BTEQ job (session mode). Standardises the customer master.
CREATE MULTISET TABLE stg_customers AS (
    SELECT
        cust_id,
        TRIM(cust_code) AS cust_code,
        UPPER(TRIM(first_name)) || ' ' || UPPER(TRIM(last_name)) AS full_name,
        CASE
            WHEN segment = 'gold' THEN 'GOLD'
            WHEN segment = 'silver' THEN 'SILVER'
            ELSE 'STANDARD'
        END AS segment_std,
        ZEROIFNULL(credit_limit) AS credit_limit,
        SUBSTR(email, INDEX(email, '@') + 1) AS email_domain,
        signup_date
    FROM customers
) WITH DATA PRIMARY INDEX (cust_id);
