CREATE TABLE category_lines_04 AS
SELECT
    ol.order_id,
    ol.line_no,
    ol.qty,
    ol.qty * ol.unit_price AS line_amount
FROM order_lines AS ol
INNER JOIN products AS p
    ON lower(rtrim(ol.sku)) = lower(rtrim(p.sku))
WHERE lower(rtrim(p.category)) = lower(rtrim('garden'));