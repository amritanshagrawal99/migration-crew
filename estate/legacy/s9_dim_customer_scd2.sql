-- OUTPUT: dim_customer
-- KEY: cust_id, start_date
-- Teradata BTEQ job. Type-2 customer dimension: close changed rows, open new versions, add new customers.
-- dim_customer_prev is yesterday's dimension; segment values in it were entered by hand over the years.
CREATE VOLATILE TABLE chg AS (
    SELECT s.cust_id, s.segment_std
    FROM stg_customers s
    INNER JOIN dim_customer_prev d
        ON s.cust_id = d.cust_id
       AND d.is_current = 'Y'
    WHERE s.segment_std <> d.segment
) WITH DATA ON COMMIT PRESERVE ROWS;

CREATE MULTISET TABLE dim_customer AS dim_customer_prev WITH DATA;

UPDATE dim_customer
FROM chg, etl_control r
SET end_date = r.run_date - 1,
    is_current = 'N'
WHERE dim_customer.cust_id = chg.cust_id
  AND dim_customer.is_current = 'Y';

INSERT INTO dim_customer (cust_id, segment, start_date, end_date, is_current)
SELECT chg.cust_id, chg.segment_std, r.run_date, DATE '9999-12-31', 'Y'
FROM chg CROSS JOIN etl_control r;

INSERT INTO dim_customer (cust_id, segment, start_date, end_date, is_current)
SELECT s.cust_id, s.segment_std, r.run_date, DATE '9999-12-31', 'Y'
FROM stg_customers s CROSS JOIN etl_control r
WHERE NOT EXISTS (SELECT 1 FROM dim_customer_prev d WHERE d.cust_id = s.cust_id);
