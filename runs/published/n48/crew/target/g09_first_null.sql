CREATE TABLE first_ship_09 AS
SELECT cust_id, order_id, ship_date
FROM orders
QUALIFY ROW_NUMBER() OVER (PARTITION BY cust_id ORDER BY ship_date ASC NULLS FIRST, order_id ASC NULLS FIRST) = 1;