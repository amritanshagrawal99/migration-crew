-- Teradata sorts NULLs first in ascending order; DuckDB defaults to NULLS LAST, so make it explicit.
-- order_id is unique, so (ship_date, order_id) is a total order: no tie-breaker needed.
CREATE TABLE first_fulfilment AS
SELECT cust_id, order_id, ship_date
FROM stg_orders
QUALIFY ROW_NUMBER() OVER (PARTITION BY cust_id ORDER BY ship_date ASC NULLS FIRST, order_id ASC NULLS FIRST) = 1;