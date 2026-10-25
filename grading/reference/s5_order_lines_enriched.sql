-- Teradata pads the shorter operand when comparing character strings (trailing spaces ignored), case-insensitive.
CREATE TABLE order_lines_enriched AS
SELECT
    ol.order_id,
    ol.line_no,
    p.sku,
    p.category,
    ol.qty,
    ol.unit_price,
    ol.qty * ol.unit_price AS line_amount
FROM order_lines ol
INNER JOIN products p
    ON upper(rtrim(ol.sku)) = upper(rtrim(p.sku));
