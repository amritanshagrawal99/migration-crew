-- Case-insensitive, trailing-space-insensitive comparison; DECIMAL cast rounds half to even (RoundHalfwayMagUp=FALSE).
CREATE TABLE lines_status_37 AS
SELECT o.cust_id, SUM(c.line_amount) AS amount, CAST(round_even(SUM(c.line_amount), 1) AS DECIMAL(14,1)) AS amount_1dp
FROM category_lines_28 c
INNER JOIN orders o ON c.order_id = o.order_id
WHERE upper(rtrim(o.status, ' ')) = upper(rtrim('shipped', ' '))
GROUP BY o.cust_id;