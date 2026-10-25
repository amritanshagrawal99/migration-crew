"""Build the legacy estate's data: python estate/build.py

    estate/data_a.duckdb      source tables, dataset A (the agents can query these)
    estate/golden_a.duckdb    the legacy system's outputs on dataset A (the agents see only diffs against them)
    grading/data_b.duckdb     dataset B: another seed, more rows (hidden; final grading only)
    grading/golden_b.duckdb   legacy outputs on dataset B (hidden)

"Legacy outputs" are produced by grading/reference/*.sql: DuckDB SQL that reproduces the Teradata semantics of the
scripts in estate/legacy/ (session-mode string comparison, NULLs sorting first, INTEGER division, TOP WITH TIES).
Both datasets contain every pattern that makes those semantics matter, so the differences show up in dataset A, and
a conversion that only patches dataset A's numbers fails on dataset B.
"""
from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
LEGACY = ROOT / "estate" / "legacy"
REFERENCE = ROOT / "grading" / "reference"
RUN_DATE = dt.date(2026, 10, 24)
SCRIPTS = sorted(p.stem for p in LEGACY.glob("s*.sql"))
SEGMENT_FORMS = {"GOLD": ["Gold", "GOLD", "gold ", "Gold   "], "SILVER": ["Silver", "silver", "SILVER "],
                 "STANDARD": ["Standard", "standard", "", None, "Std"]}
STATUS = ["shipped", "Shipped", "SHIPPED ", "delivered", "Delivered", "pending", "Pending ", "cancelled"]
CHANNEL = ["WEB", "web", "Web  ", "APP", "app ", "App", "STORE", "store", "kiosk"]
CATEGORIES = ["books", "electronics", "home", "toys", "garden"]
# Spellings that appear ONLY in dataset B: a conversion that lists dataset A's spellings instead of implementing
# Teradata's comparison rules passes on A and fails here.
EXTRA_B = {"segment": {"GOLD": ["gOLD", "GoLd     "], "SILVER": ["sILVER", "Silver      "]},
           "status": ["sHIPPED", "DELIVERED      ", "delivered "], "channel": ["wEB", "APP      ", "Web"]}


def generate(seed: int, n_customers: int, extra: bool = False) -> dict[str, tuple[list[str], list[tuple]]]:
    rng = random.Random(seed)
    seg_forms = {k: v + (EXTRA_B["segment"].get(k, []) if extra else []) for k, v in SEGMENT_FORMS.items()}
    shipped_status = STATUS[:5] + (EXTRA_B["status"] if extra else [])
    channels = CHANNEL + (EXTRA_B["channel"] if extra else [])
    products = [(f"SKU{i:04d}", rng.choice(CATEGORIES), Decimal(rng.randint(199, 9999)) / 100) for i in range(1, 41)]
    customers, orders, lines, prev = [], [], [], []
    oid = 1
    for cid in range(1, n_customers + 1):
        seg = rng.choices(["GOLD", "SILVER", "STANDARD"], [2, 3, 5])[0]
        seg_raw = rng.choice(seg_forms[seg])
        first, last = rng.choice(["asha", " Ravi", "meera ", "John", "li"]), rng.choice(["rao", "Iyer ", " Khan", "smith"])
        customers.append((cid, f"C{cid:05d}   ", first, last, seg_raw,
                          None if rng.random() < 0.2 else Decimal(rng.randint(100, 9000)) * 10,
                          f"{first.strip().lower()}.{cid}@{rng.choice(['mail.com', 'corp.in', 'shop.co'])}",
                          dt.date(2024, 1, 1) + dt.timedelta(days=rng.randint(0, 900))))
        # yesterday's dimension: same segment written by hand in another case, or a genuinely different segment
        if rng.random() < 0.85:
            changed = rng.random() < 0.2
            prev_seg = rng.choice([s for s in SEGMENT_FORMS if s != seg]) if changed else seg
            prev_raw = rng.choice([f for f in SEGMENT_FORMS[prev_seg] if f]) if prev_seg != "STANDARD" else "STANDARD"
            start = dt.date(2025, 1, 1) + dt.timedelta(days=rng.randint(0, 300))
            if rng.random() < 0.3:   # an older, closed version
                prev.append((cid, rng.choice(["Silver", "Standard"]), dt.date(2024, 6, 1), start - dt.timedelta(days=1), "N"))
            prev.append((cid, prev_raw.strip() if rng.random() < 0.5 else prev_raw, start, dt.date(9999, 12, 31),
                         "y" if rng.random() < 0.1 else "Y"))
        for _ in range(rng.choice([0, 1, 1, 2, 3, 4, 5, 6, 8])):
            od = dt.date(2026, 1, 1) + dt.timedelta(days=rng.randint(0, 296))
            shipped = rng.random() > 0.18
            orders.append((oid, cid, od, od + dt.timedelta(days=rng.randint(0, 9)) if shipped else None,
                           rng.choice(shipped_status) if shipped else rng.choice(STATUS[5:]), rng.choice(channels),
                           rng.randint(1, 9), Decimal(rng.randint(500, 90000)) / 100))
            for ln in range(1, rng.randint(1, 4) + 1):
                sku, _, price = rng.choice(products)
                code = sku.lower() if rng.random() < 0.1 else (sku.title() if extra and rng.random() < 0.1 else sku)
                lines.append((oid, ln, code.ljust(10), rng.randint(1, 5), price))
            oid += 1
    return {
        "customers": (["cust_id INTEGER", "cust_code VARCHAR", "first_name VARCHAR", "last_name VARCHAR", "segment VARCHAR",
                       "credit_limit DECIMAL(12,2)", "email VARCHAR", "signup_date DATE"], customers),
        "orders": (["order_id INTEGER", "cust_id INTEGER", "order_date DATE", "ship_date DATE", "status VARCHAR",
                    "channel VARCHAR", "total_items INTEGER", "amount DECIMAL(12,2)"], orders),
        "order_lines": (["order_id INTEGER", "line_no INTEGER", "sku VARCHAR", "qty INTEGER", "unit_price DECIMAL(12,2)"], lines),
        "products": (["sku VARCHAR", "category VARCHAR", "list_price DECIMAL(12,2)"], products),
        "dim_customer_prev": (["cust_id INTEGER", "segment VARCHAR", "start_date DATE", "end_date DATE", "is_current VARCHAR"], prev),
        "etl_control": (["run_date DATE"], [(RUN_DATE,)]),
    }


def write_sources(path: Path, tables) -> None:
    path.unlink(missing_ok=True)
    con = duckdb.connect(str(path), config={"storage_compatibility_version": "v1.0.0"})
    for name, (cols, rows) in tables.items():
        con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        if rows:
            con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", rows)
    con.close()


def run_scripts(sources: Path, scripts: dict[str, str]) -> duckdb.DuckDBPyConnection:
    """Load `sources` into memory and run `scripts` (name -> DuckDB SQL) in order."""
    con = duckdb.connect()
    con.execute(f"ATTACH '{sources.as_posix()}' AS src (READ_ONLY)")
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 'src'").fetchall():
        con.execute(f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"')
    con.execute("DETACH src")
    for sql in scripts.values():
        con.execute(sql)
    return con


def output_of(script: str) -> tuple[str, list[str]]:
    head = (LEGACY / f"{script}.sql").read_text().splitlines()
    table = next(line.split(":", 1)[1].strip() for line in head if line.startswith("-- OUTPUT:"))
    key = [k.strip() for k in next(line.split(":", 1)[1] for line in head if line.startswith("-- KEY:")).split(",")]
    return table, key


def write_golden(sources: Path, golden: Path) -> dict[str, int]:
    ref = {s: (REFERENCE / f"{s}.sql").read_text() for s in SCRIPTS}
    con = run_scripts(sources, ref)
    golden.unlink(missing_ok=True)
    con.execute(f"ATTACH '{golden.as_posix()}' AS g (STORAGE_VERSION 'v1.0.0')")
    counts = {}
    for s in SCRIPTS:
        table, _ = output_of(s)
        con.execute(f'CREATE TABLE g."{table}" AS SELECT * FROM "{table}"')
        counts[table] = con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    con.close()
    return counts


if __name__ == "__main__":
    for label, seed, n, data, gold in (("A", 11, 300, ROOT / "estate" / "data_a.duckdb", ROOT / "estate" / "golden_a.duckdb"),
                                       ("B", 29, 520, ROOT / "grading" / "data_b.duckdb", ROOT / "grading" / "golden_b.duckdb")):
        write_sources(data, generate(seed, n, extra=label == "B"))
        print(label, write_golden(data, gold))
