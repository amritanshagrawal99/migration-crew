-- Traps (Teradata session mode, character comparisons are case-insensitive and ignore trailing spaces):
--  * is_current = 'Y' also matches hand-entered 'y' rows.
--  * segment_std <> segment treats 'Gold   ', 'gold', 'GOLD' as equal (no change detected).
CREATE TEMP TABLE chg AS
SELECT s.cust_id, s.segment_std
FROM stg_customers s
INNER JOIN dim_customer_prev d
    ON s.cust_id = d.cust_id
   AND LOWER(RTRIM(d.is_current)) = LOWER(RTRIM('Y'))
WHERE LOWER(RTRIM(s.segment_std)) <> LOWER(RTRIM(d.segment));

CREATE TABLE dim_customer AS SELECT * FROM dim_customer_prev;

UPDATE dim_customer
SET end_date = r.run_date - 1,
    is_current = 'N'
FROM chg, etl_control r
WHERE dim_customer.cust_id = chg.cust_id
  AND LOWER(RTRIM(dim_customer.is_current)) = LOWER(RTRIM('Y'));

INSERT INTO dim_customer (cust_id, segment, start_date, end_date, is_current)
SELECT chg.cust_id, chg.segment_std, r.run_date, DATE '9999-12-31', 'Y'
FROM chg CROSS JOIN etl_control r;

INSERT INTO dim_customer (cust_id, segment, start_date, end_date, is_current)
SELECT s.cust_id, s.segment_std, r.run_date, DATE '9999-12-31', 'Y'
FROM stg_customers s CROSS JOIN etl_control r
WHERE NOT EXISTS (SELECT 1 FROM dim_customer_prev d WHERE d.cust_id = s.cust_id);