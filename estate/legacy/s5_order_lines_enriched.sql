-- OUTPUT: order_lines_enriched
-- KEY: order_id, line_no
-- Teradata BTEQ job. Order lines joined to the product catalogue.
-- order_lines.sku is CHAR(10), loaded from a fixed-width mainframe extract.
CREATE MULTISET TABLE order_lines_enriched AS (
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
        ON ol.sku = p.sku
) WITH DATA PRIMARY INDEX (order_id, line_no);
