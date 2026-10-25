-- Teradata session mode: character comparisons are NOT CASESPECIFIC and ignore trailing pad spaces.
-- Every text comparison is done on UPPER(RTRIM(x, ' ')) on both sides; NULLs propagate as in the legacy SQL.
CREATE OR REPLACE TEMP TABLE chg AS
SELECT s.cust_id, s.segment_std
FROM stg_customers s
INNER JOIN dim_customer_prev d
    ON s.cust_id = d.cust_id
   AND UPPER(RTRIM(d.is_current, ' ')) = UPPER(RTRIM('Y', ' '))
WHERE UPPER(RTRIM(s.segment_std, ' ')) <> UPPER(RTRIM(d.segment, ' '));

CREATE OR REPLACE TABLE dim_customer AS
SELECT * FROM dim_customer_prev;

-- Teradata DATE - integer = date minus N days
UPDATE dim_customer
SET end_date = CAST(r.run_date AS DATE) - 1,
    is_current = 'N'
FROM chg, etl_control r
WHERE dim_customer.cust_id = chg.cust_id
  AND UPPER(RTRIM(dim_customer.is_current, ' ')) = UPPER(RTRIM('Y', ' '));

INSERT INTO dim_customer (cust_id, segment, start_date, end_date, is_current)
SELECT chg.cust_id, chg.segment_std, CAST(r.run_date AS DATE), DATE '9999-12-31', 'Y'
FROM chg CROSS JOIN etl_control r;

INSERT INTO dim_customer (cust_id, segment, start_date, end_date, is_current)
SELECT s.cust_id, s.segment_std, CAST(r.run_date AS DATE), DATE '9999-12-31', 'Y'
FROM stg_customers s CROSS JOIN etl_control r
WHERE NOT EXISTS (SELECT 1 FROM dim_customer_prev d WHERE d.cust_id = s.cust_id);
