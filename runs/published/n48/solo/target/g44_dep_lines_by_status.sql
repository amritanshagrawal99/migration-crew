-- Case-insensitive, trailing-space-insensitive comparison; DECIMAL cast rounds half to even (RoundHalfwayMagUp=FALSE).
CREATE TABLE lines_status_44 AS
SELECT o.cust_id, SUM(c.line_amount) AS amount, CAST(round_even(SUM(c.line_amount), 1) AS DECIMAL(14,1)) AS amount_1dp
FROM category_lines_04 c
INNER JOIN orders o ON c.order_id = o.order_id
WHERE upper(rtrim(o.status, ' ')) = upper(rtrim('Delivered', ' '))
GROUP BY o.cust_id;