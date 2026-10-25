-- Teradata session mode: join on CHAR(10) sku vs VARCHAR sku pads/ignores trailing spaces and is case-insensitive;
-- category filter likewise.
CREATE TABLE category_lines_28 AS
SELECT ol.order_id, ol.line_no, ol.qty, ol.qty * ol.unit_price AS line_amount
FROM order_lines ol
INNER JOIN products p ON upper(rtrim(ol.sku, ' ')) = upper(rtrim(p.sku, ' '))
WHERE upper(rtrim(p.category, ' ')) = upper(rtrim('books', ' '));