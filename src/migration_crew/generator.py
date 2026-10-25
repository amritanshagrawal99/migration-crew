"""Generate a larger estate from templates: migration-crew generate --scripts 48 --out estates/n48

Each template family writes a Teradata script AND its DuckDB reference (the legacy semantics, implemented exactly),
so every generated pair is correct by construction. Literals, columns and thresholds are drawn from a seed. Later
scripts read earlier scripts' outputs, so the estate is a dependency graph, not a flat list.

    trap families     case/space-insensitive filters, IN lists and joins; half-even rounding; TOP WITH TIES; ZEROIFNULL
    control families  integer division, NULL ordering, date arithmetic: the auto-converter already handles these
    dependent         read another script's output (and add a trap of their own)

Layout: <out>/estate/{legacy/, data_a.duckdb, golden_a.duckdb} and <out>/grading/{reference/, data_b.duckdb,
golden_b.duckdb, manifest.json}. Datasets are the same generator as the hand-built estate (A: seed 11, B: seed 29 with
spellings A lacks).
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from . import datagen

SEGMENTS = ["gold", "silver"]
STATUSES = ["shipped", "delivered", "pending"]          # each has case/space variants in the data
CHANNELS = ["WEB", "APP", "STORE"]
CATEGORIES = ["books", "electronics", "home", "toys", "garden"]
PLATFORM_NOTES = """# Legacy platform notes

- Teradata 17.20. All jobs run through BTEQ in Teradata (session) mode, not ANSI mode.
- DBS Control: RoundHalfwayMagUp = FALSE (the default).
- Character data in the source tables comes from fixed-width extracts and hand-maintained reference tables, so
  values can carry trailing spaces and inconsistent letter case.
- Each job writes one output table, named in its `-- OUTPUT:` header, keyed by its `-- KEY:` header.
- Target platform: DuckDB. The migrated jobs must reproduce the legacy outputs exactly, row for row.
"""


def _case(rng: random.Random, word: str) -> str:
    return rng.choice([word.lower(), word.upper(), word.title()])


def _eq(col: str, lit: str) -> str:
    """Teradata session-mode equality, exactly: case- and trailing-space-insensitive."""
    return f"upper(rtrim({col})) = '{lit.upper()}'"


def _half_even_1dp(expr: str) -> str:
    """CAST(<scale-2 decimal> AS DECIMAL(14,1)) under RoundHalfwayMagUp=FALSE, in exact integer arithmetic."""
    c = f"CAST(({expr}) * 100 AS BIGINT)"
    return (f"CAST(({c} // 10 + CASE WHEN {c} % 10 > 5 THEN 1 WHEN {c} % 10 = 5 THEN ({c} // 10) % 2 ELSE 0 END) "
            f"AS DECIMAL(14, 0)) / 10")


@dataclass
class Gen:
    name: str
    family: str
    output: str
    key: list[str]
    legacy: str
    reference: str
    traps: list[str]


def _wrap(out: str, key: list[str], body: str, comment: str) -> str:
    return (f"-- OUTPUT: {out}\n-- KEY: {', '.join(key)}\n-- Teradata BTEQ job (session mode). {comment}\n"
            f"CREATE MULTISET TABLE {out} AS (\n{body}\n) WITH DATA PRIMARY INDEX ({', '.join(key)});\n")


def _ref(out: str, body: str) -> str:
    return f"CREATE TABLE {out} AS\n{body};\n"


# ------------------------------------------------------------------ families (i = script number, rng = seeded)

def seg_filter(i, rng, outs):
    seg = rng.choice(SEGMENTS)
    lit = _case(rng, seg)
    out = f"seg_{seg}_{i:02d}"
    legacy = (f"    SELECT cust_id, TRIM(cust_code) AS cust_code, signup_date\n    FROM customers\n"
              f"    WHERE segment = '{lit}'")
    ref = f"SELECT cust_id, trim(cust_code) AS cust_code, signup_date FROM customers WHERE {_eq('segment', seg)}"
    return Gen("", "seg_filter", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, f"{seg.title()} customers."),
               _ref(out, ref), ["case_pad"])


def status_counts(i, rng, outs):
    sts = rng.sample(STATUSES, rng.randint(1, 2))
    lits = ", ".join(f"'{_case(rng, s)}'" for s in sts)
    out = f"status_counts_{i:02d}"
    legacy = (f"    SELECT cust_id, COUNT(*) AS order_cnt,\n"
              f"           SUM(CASE WHEN status IN ({lits}) THEN 1 ELSE 0 END) AS match_cnt\n"
              f"    FROM orders\n    GROUP BY cust_id")
    in_ref = ", ".join(f"'{s.upper()}'" for s in sts)
    ref = (f"SELECT cust_id, count(*) AS order_cnt, sum(CASE WHEN upper(rtrim(status)) IN ({in_ref}) THEN 1 ELSE 0 END) "
           f"AS match_cnt FROM orders GROUP BY cust_id")
    return Gen("", "status_counts", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, f"Orders per customer in status {', '.join(sts)}."),
               _ref(out, ref), ["case_pad"])


def channel_revenue(i, rng, outs):
    ch = rng.choice(CHANNELS)
    out = f"channel_revenue_{i:02d}"
    legacy = (f"    SELECT cust_id, SUM(amount) AS revenue, COUNT(*) AS order_cnt\n    FROM orders\n"
              f"    WHERE channel = '{_case(rng, ch)}'\n    GROUP BY cust_id")
    ref = f"SELECT cust_id, sum(amount) AS revenue, count(*) AS order_cnt FROM orders WHERE {_eq('channel', ch)} GROUP BY cust_id"
    return Gen("", "channel_revenue", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, f"{ch} revenue per customer."),
               _ref(out, ref), ["case_pad"])


def category_lines(i, rng, outs):
    cat = rng.choice(CATEGORIES)
    out = f"category_lines_{i:02d}"
    legacy = (f"    SELECT ol.order_id, ol.line_no, ol.qty, ol.qty * ol.unit_price AS line_amount\n"
              f"    FROM order_lines ol\n    INNER JOIN products p ON ol.sku = p.sku\n"
              f"    WHERE p.category = '{_case(rng, cat)}'")
    ref = (f"SELECT ol.order_id, ol.line_no, ol.qty, ol.qty * ol.unit_price AS line_amount FROM order_lines ol "
           f"INNER JOIN products p ON upper(rtrim(ol.sku)) = upper(rtrim(p.sku)) WHERE {_eq('p.category', cat)}")
    return Gen("", "category_lines", out, ["order_id", "line_no"],
               _wrap(out, ["order_id", "line_no"], legacy, f"Order lines in category {cat}; order_lines.sku is CHAR(10)."),
               _ref(out, ref), ["case_pad", "pad_join"])


def rounding(i, rng, outs):
    month = rng.randint(1, 8)
    out = f"value_1dp_{i:02d}"
    legacy = (f"    SELECT cust_id, CAST(SUM(amount) AS DECIMAL(14,1)) AS value_1dp\n    FROM orders\n"
              f"    WHERE order_date >= DATE '2026-{month:02d}-01'\n    GROUP BY cust_id")
    ref = (f"SELECT cust_id, {_half_even_1dp('sum(amount)')} AS value_1dp FROM orders "
           f"WHERE order_date >= DATE '2026-{month:02d}-01' GROUP BY cust_id")
    return Gen("", "rounding", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, "Order value since a month, 1 dp."),
               _ref(out, ref), ["half_even"])


def topk(i, rng, outs):
    k = rng.choice([5, 10, 15])
    metric, ref_metric = rng.choice([("COUNT(*)", "count(*)"), ("SUM(total_items)", "sum(total_items)")])
    out = f"top{k}_{i:02d}"
    legacy = (f"    SELECT TOP {k} WITH TIES cust_id, {metric} AS metric\n    FROM orders\n    GROUP BY cust_id\n"
              f"    ORDER BY metric DESC")
    ref = f"SELECT cust_id, {ref_metric} AS metric FROM orders GROUP BY cust_id QUALIFY rank() OVER (ORDER BY {ref_metric} DESC) <= {k}"
    return Gen("", "topk", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, f"Top {k} customers, keeping ties."),
               _ref(out, ref), ["top_with_ties"])


def zeroifnull(i, rng, outs):
    t = rng.choice([20000, 40000, 60000])
    out = f"credit_band_{i:02d}"
    legacy = (f"    SELECT cust_id, ZEROIFNULL(credit_limit) AS credit_limit,\n"
              f"           CASE WHEN ZEROIFNULL(credit_limit) > {t} THEN 'HIGH' ELSE 'LOW' END AS band\n    FROM customers")
    ref = (f"SELECT cust_id, coalesce(credit_limit, 0) AS credit_limit, CASE WHEN coalesce(credit_limit, 0) > {t} "
           f"THEN 'HIGH' ELSE 'LOW' END AS band FROM customers")
    return Gen("", "zeroifnull", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, "Credit band."), _ref(out, ref), ["zeroifnull"])


def ratio(i, rng, outs):
    out = f"items_ratio_{i:02d}"
    legacy = ("    SELECT cust_id, CAST(SUM(total_items) AS INTEGER) / CAST(COUNT(*) AS INTEGER) AS items_per_order\n"
              "    FROM orders\n    GROUP BY cust_id")
    ref = "SELECT cust_id, CAST(sum(total_items) AS BIGINT) // CAST(count(*) AS BIGINT) AS items_per_order FROM orders GROUP BY cust_id"
    return Gen("", "ratio", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, "Items per order."), _ref(out, ref), [])


def first_null(i, rng, outs):
    out = f"first_ship_{i:02d}"
    legacy = ("    SELECT cust_id, order_id, ship_date\n    FROM orders\n"
              "    QUALIFY ROW_NUMBER() OVER (PARTITION BY cust_id ORDER BY ship_date ASC, order_id ASC) = 1")
    ref = ("SELECT cust_id, order_id, ship_date FROM orders QUALIFY row_number() OVER (PARTITION BY cust_id "
           "ORDER BY ship_date ASC NULLS FIRST, order_id ASC) = 1")
    return Gen("", "first_null", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, "First order in fulfilment order."),
               _ref(out, ref), [])


def recency(i, rng, outs):
    t = rng.choice([30, 60, 90])
    out = f"recency_{i:02d}"
    legacy = (f"    SELECT o.cust_id, r.run_date - MAX(o.order_date) AS days_since,\n"
              f"           CASE WHEN r.run_date - MAX(o.order_date) > {t} THEN 1 ELSE 0 END AS lapsed\n"
              f"    FROM orders o CROSS JOIN etl_control r\n    GROUP BY o.cust_id, r.run_date")
    ref = (f"SELECT o.cust_id, r.run_date - max(o.order_date) AS days_since, CASE WHEN r.run_date - max(o.order_date) > {t} "
           f"THEN 1 ELSE 0 END AS lapsed FROM orders o CROSS JOIN etl_control r GROUP BY o.cust_id, r.run_date")
    return Gen("", "recency", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, f"Lapsed after {t} days."), _ref(out, ref), [])


def dep_seg_orders(i, rng, outs):
    src = rng.choice(outs["seg_filter"])
    st = rng.choice(STATUSES)
    out = f"seg_orders_{i:02d}"
    legacy = (f"    SELECT f.cust_id, COUNT(*) AS order_cnt\n    FROM {src} f\n    INNER JOIN orders o ON f.cust_id = o.cust_id\n"
              f"    WHERE o.status = '{_case(rng, st)}'\n    GROUP BY f.cust_id")
    ref = (f"SELECT f.cust_id, count(*) AS order_cnt FROM {src} f INNER JOIN orders o ON f.cust_id = o.cust_id "
           f"WHERE {_eq('o.status', st)} GROUP BY f.cust_id")
    return Gen("", "dep_seg_orders", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, f"{st} orders of the customers in {src}."),
               _ref(out, ref), ["case_pad"])


def dep_round_rank(i, rng, outs):
    src = rng.choice(outs["rounding"])
    k = rng.choice([5, 10])
    out = f"top_value_{i:02d}"
    legacy = (f"    SELECT TOP {k} WITH TIES cust_id, value_1dp\n    FROM {src}\n    ORDER BY value_1dp DESC")
    ref = f"SELECT cust_id, value_1dp FROM {src} QUALIFY rank() OVER (ORDER BY value_1dp DESC) <= {k}"
    return Gen("", "dep_round_rank", out, ["cust_id"], _wrap(out, ["cust_id"], legacy, f"Top {k} by the rounded value in {src}."),
               _ref(out, ref), ["top_with_ties"])


def dep_lines_by_status(i, rng, outs):
    src = rng.choice(outs["category_lines"])
    st = rng.choice(["shipped", "delivered"])
    out = f"lines_status_{i:02d}"
    legacy = (f"    SELECT o.cust_id, SUM(c.line_amount) AS amount, CAST(SUM(c.line_amount) AS DECIMAL(14,1)) AS amount_1dp\n"
              f"    FROM {src} c\n    INNER JOIN orders o ON c.order_id = o.order_id\n"
              f"    WHERE o.status = '{_case(rng, st)}'\n    GROUP BY o.cust_id")
    ref = (f"SELECT o.cust_id, sum(c.line_amount) AS amount, {_half_even_1dp('sum(c.line_amount)')} AS amount_1dp FROM {src} c "
           f"INNER JOIN orders o ON c.order_id = o.order_id WHERE {_eq('o.status', st)} GROUP BY o.cust_id")
    return Gen("", "dep_lines_by_status", out, ["cust_id"],
               _wrap(out, ["cust_id"], legacy, f"{st} line amounts per customer from {src}."), _ref(out, ref), ["case_pad", "half_even"])


BASE = {seg_filter: 3, status_counts: 3, channel_revenue: 3, category_lines: 3, rounding: 3, topk: 2, zeroifnull: 2,
        ratio: 1, first_null: 1, recency: 1}              # weights: most legacy jobs carry at least one trap
DEPENDENT = {dep_seg_orders: "seg_filter", dep_round_rank: "rounding", dep_lines_by_status: "category_lines"}


def _signature(g: Gen) -> str:
    return g.legacy.replace(g.output, "?")


def generate_estate(n: int, seed: int = 7) -> list[Gen]:
    """n scripts: every base family once, then weighted base families, then ~35% dependent scripts. No two scripts
    are the same job under another name."""
    rng = random.Random(seed)
    gens: list[Gen] = []
    outs: dict[str, list[str]] = {}
    seen: set[str] = set()
    base = list(BASE)
    n_base = max(len(base), round(n * 0.65))
    for i in range(1, n + 1):
        for _ in range(50):
            if i <= len(base):
                fam = base[i - 1]
            elif i <= n_base:
                fam = rng.choices(base, [BASE[f] for f in base])[0]
            else:
                fam = rng.choice([f for f, need in DEPENDENT.items() if outs.get(need)])
            g = fam(i, rng, outs)
            if _signature(g) not in seen:
                break
        seen.add(_signature(g))
        g.name = f"g{i:02d}_{g.family}"
        outs.setdefault(g.family, []).append(g.output)
        gens.append(g)
    return gens


def write(out_dir: Path, n: int, seed: int = 7) -> dict:
    gens = generate_estate(n, seed)
    est, grd = out_dir / "estate", out_dir / "grading"
    (est / "legacy").mkdir(parents=True, exist_ok=True)
    (grd / "reference").mkdir(parents=True, exist_ok=True)
    for old in list((est / "legacy").glob("*.sql")) + list((grd / "reference").glob("*.sql")):
        old.unlink()
    for g in gens:
        (est / "legacy" / f"{g.name}.sql").write_text(g.legacy)
        (grd / "reference" / f"{g.name}.sql").write_text(g.reference)
    (est / "legacy" / "PLATFORM_NOTES.md").write_text(PLATFORM_NOTES)
    refs = {g.name: g.reference for g in gens}
    counts = {}
    for label, seed_, size, data, gold in (("A", 11, 300, est / "data_a.duckdb", est / "golden_a.duckdb"),
                                           ("B", 29, 520, grd / "data_b.duckdb", grd / "golden_b.duckdb")):
        datagen.write_sources(data, datagen.generate(seed_, size, extra=label == "B"))
        counts[label] = datagen.write_golden(data, gold, refs, {g.name: g.output for g in gens})
    manifest = {"scripts": n, "seed": seed, "families": {g.name: g.family for g in gens},
                "traps": {g.name: g.traps for g in gens}, "rows": counts}
    (grd / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
