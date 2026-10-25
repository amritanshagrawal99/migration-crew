-- TOP 10 WITH TIES: keep every row whose order_cnt ties with the 10th row (RANK <= 10), not ROW_NUMBER.
-- Teradata sorts NULLs last in DESC order; made explicit with NULLS LAST.
-- cust_id is an integer key on both sides, so the join has no text-comparison semantics.
CREATE TABLE top_customers AS
SELECT cust_id, full_name, segment_std, order_cnt, lifetime_value
FROM (
    SELECT
        s.cust_id,
        c.full_name,
        c.segment_std,
        s.order_cnt,
        s.lifetime_value,
        RANK() OVER (ORDER BY s.order_cnt DESC NULLS LAST) AS rnk
    FROM customer_order_stats s
    INNER JOIN stg_customers c
        ON s.cust_id = c.cust_id
) t
WHERE rnk <= 10;