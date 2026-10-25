-- OUTPUT: first_fulfilment
-- KEY: cust_id
-- Teradata BTEQ job. The first order per customer in fulfilment order.
CREATE MULTISET TABLE first_fulfilment AS (
    SELECT cust_id, order_id, ship_date
    FROM stg_orders
    QUALIFY ROW_NUMBER() OVER (PARTITION BY cust_id ORDER BY ship_date ASC, order_id ASC) = 1
) WITH DATA PRIMARY INDEX (cust_id);
