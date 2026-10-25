-- Teradata session mode: string comparisons are NOT CASESPECIFIC and ignore trailing spaces.
-- CAST to DECIMAL(14,1) rounds half-to-even (RoundHalfwayMagUp=FALSE): exact integer arithmetic on the scale-2 sum.
CREATE OR REPLACE TABLE lines_status_45 AS
WITH s AS (
    SELECT o.cust_id,
           SUM(c.line_amount) AS amount,
           CAST(SUM(c.line_amount) * 100 AS HUGEINT) AS cents
    FROM category_lines_28 AS c
    INNER JOIN orders AS o
        ON c.order_id = o.order_id
    WHERE lower(rtrim(o.status, ' ')) = lower(rtrim('DELIVERED', ' '))
    GROUP BY o.cust_id
), q AS (
    SELECT cust_id, amount, sign(cents) AS sg, abs(cents) // 10 AS qt, abs(cents) % 10 AS rm
    FROM s
)
SELECT cust_id,
       amount,
       CAST(CAST(sg * (qt + CASE WHEN rm > 5 OR (rm = 5 AND qt % 2 = 1) THEN 1 ELSE 0 END) AS DECIMAL(37,0))
            * CAST(0.1 AS DECIMAL(2,1)) AS DECIMAL(14,1)) AS amount_1dp
FROM q;