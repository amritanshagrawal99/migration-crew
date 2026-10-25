-- Teradata sorts NULLs first in ascending order.
CREATE TABLE first_fulfilment AS
SELECT cust_id, order_id, ship_date
FROM stg_orders
QUALIFY row_number() OVER (PARTITION BY cust_id ORDER BY ship_date ASC NULLS FIRST, order_id ASC) = 1;
