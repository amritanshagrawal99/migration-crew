-- Teradata session mode: character comparisons are NOT CASESPECIFIC and ignore trailing
-- spaces (order_lines.sku is CHAR(10), padded). Normalise both sides of the join key;
-- output keeps p.sku as stored, as legacy does.
CREATE TABLE order_lines_enriched AS
SELECT
    ol.order_id,
    ol.line_no,
    p.sku,
    p.category,
    ol.qty,
    ol.unit_price,
    ol.qty * ol.unit_price AS line_amount
FROM order_lines AS ol
INNER JOIN products AS p
    ON upper(rtrim(ol.sku)) = upper(rtrim(p.sku));
