-- Trap: order_lines.sku is CHAR(10) padded with trailing spaces; Teradata session-mode comparison
-- ignores trailing spaces and letter case, so the join key is compared as LOWER(RTRIM(..)).
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
    ON LOWER(RTRIM(ol.sku)) = LOWER(RTRIM(p.sku));