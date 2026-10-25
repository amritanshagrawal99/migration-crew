-- TOP n WITH TIES = every row ranked <= n.
CREATE TABLE top_customers AS
SELECT s.cust_id, c.full_name, c.segment_std, s.order_cnt, s.lifetime_value
FROM customer_order_stats s
INNER JOIN stg_customers c ON s.cust_id = c.cust_id
QUALIFY rank() OVER (ORDER BY s.order_cnt DESC) <= 10;
