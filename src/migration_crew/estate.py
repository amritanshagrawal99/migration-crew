"""The migration estate: legacy scripts, datasets, and the machinery to run and reconcile converted SQL.

    run_chain(...)   load a dataset into an in-memory DuckDB, run the converted scripts a script depends on, then the
                     script itself, each from its own .sql file
    reconcile(...)   compare a script's output table with the legacy system's output, by key: row counts, missing
                     and extra keys, and per-column differences with sample rows

Comparison is exact, with normalisation only where two engines legitimately differ in representation: numbers by
value (so DECIMAL 3 and BIGINT 3 match) and rows independent of order.
"""
from __future__ import annotations

import functools
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]


def estate_dir() -> Path:
    """The estate the crew works on: legacy/ + data_a.duckdb + golden_a.duckdb (MIGRATION_CREW_ESTATE)."""
    return Path(os.environ.get("MIGRATION_CREW_ESTATE", ROOT / "estate")).resolve()


def grading_dir() -> Path:
    """Hidden grading data for that estate, next to it: ../grading/{data_b,golden_b}.duckdb + reference/."""
    return estate_dir().parent / "grading"


def legacy_dir() -> Path:
    return estate_dir() / "legacy"


@dataclass
class Script:
    name: str
    output: str
    key: list[str]
    reads: list[str]            # tables the legacy SQL reads (sources or other scripts' outputs)
    depends_on: list[str]       # scripts whose outputs this one reads


def scripts() -> dict[str, Script]:
    return dict(_scripts(str(legacy_dir())))


@functools.lru_cache(maxsize=8)
def _scripts(legacy: str) -> tuple:
    import sqlglot
    from sqlglot import exp
    raw = {}
    for p in sorted(Path(legacy).glob("*.sql")):
        text = p.read_text()
        out = re.search(r"--\s*OUTPUT:\s*(\w+)", text).group(1)
        key = [k.strip() for k in re.search(r"--\s*KEY:\s*(.+)", text).group(1).split(",")]
        tables = set()
        for stmt in sqlglot.parse(text, read="teradata"):
            if stmt is not None:
                tables |= {t.name for t in stmt.find_all(exp.Table)}
        raw[p.stem] = (out, key, tables)
    outputs = {out: name for name, (out, _, _) in raw.items()}
    temps = {"chg"}
    res = {}
    for name, (out, key, tables) in raw.items():
        reads = sorted(t for t in tables if t != out and t not in temps)
        res[name] = Script(name, out, key, reads, sorted(outputs[t] for t in reads if t in outputs and outputs[t] != name))
    return tuple(res.items())


def chain(name: str, all_scripts: dict[str, Script] | None = None) -> list[str]:
    """`name` and everything it depends on, in a valid run order."""
    s = all_scripts or scripts()
    order: list[str] = []

    def visit(n: str):
        for d in s[n].depends_on:
            visit(d)
        if n not in order:
            order.append(n)
    visit(name)
    return order


class ScriptError(Exception):
    def __init__(self, script: str, message: str):
        super().__init__(f"{script}: {message}")
        self.script, self.message = script, message


def load(dataset: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"ATTACH '{dataset.as_posix()}' AS src (READ_ONLY)")
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 'src'").fetchall():
        con.execute(f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"')
    con.execute("DETACH src")
    # Converted SQL runs with no file, network or ATTACH access: it can only see the tables loaded above.
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con


def run_chain(name: str, dataset: Path, sql_for) -> duckdb.DuckDBPyConnection:
    """Run `name` and its dependencies on a fresh copy of `dataset`. `sql_for(script) -> str | None` supplies the
    converted SQL; a dependency with no SQL yet is an error naming it."""
    s = scripts()
    con = load(dataset)
    for n in chain(name, s):
        sql = sql_for(n)
        if not sql:
            raise ScriptError(n, f"no converted SQL saved for {n} (a dependency of {name})" if n != name else "no SQL saved")
        try:
            con.execute(sql)
        except duckdb.Error as e:
            raise ScriptError(n, f"{type(e).__name__}: {str(e)[:600]}") from None
        if not con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [s[n].output]).fetchone()[0]:
            raise ScriptError(n, f"ran, but did not create its output table {s[n].output}")
    return con


@dataclass
class Diff:
    script: str
    table: str
    legacy_rows: int
    new_rows: int
    missing_keys: list[tuple] = field(default_factory=list)   # in legacy, not in new
    extra_keys: list[tuple] = field(default_factory=list)     # in new, not in legacy
    duplicate_keys: int = 0
    column_mismatches: dict[str, int] = field(default_factory=dict)
    samples: dict[str, list[tuple]] = field(default_factory=dict)   # column -> [(key, legacy value, new value)]
    missing_columns: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    n_missing: int = 0
    n_extra: int = 0

    @property
    def match(self) -> bool:
        return not (self.n_missing or self.n_extra or self.duplicate_keys or self.column_mismatches
                    or self.missing_columns or self.legacy_rows != self.new_rows)


def _norm(v):
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        return Decimal(str(v)).normalize()
    return v


def reconcile(script: Script, legacy: duckdb.DuckDBPyConnection, legacy_table: str,
              new: duckdb.DuckDBPyConnection, sample: int = 5) -> Diff:
    lcols = [r[0] for r in legacy.execute(f'DESCRIBE "{legacy_table}"').fetchall()]
    ncols = [r[0] for r in new.execute(f'DESCRIBE "{script.output}"').fetchall()]
    lrows = legacy.execute(f'SELECT * FROM "{legacy_table}"').fetchall()
    nrows = new.execute(f'SELECT * FROM "{script.output}"').fetchall()
    d = Diff(script.name, script.output, len(lrows), len(nrows),
             missing_columns=[c for c in lcols if c not in ncols], extra_columns=[c for c in ncols if c not in lcols])
    if any(k not in ncols for k in script.key):
        return d
    li = {c: i for i, c in enumerate(lcols)}
    ni = {c: i for i, c in enumerate(ncols)}

    def index(rows, idx):
        out, dups = {}, 0
        for r in rows:
            k = tuple(_norm(r[idx[c]]) for c in script.key)
            dups += k in out
            out[k] = r
        return out, dups

    def shown(k, rows, idx):
        r = rows[k]
        return tuple(r[idx[c]] for c in script.key)

    lmap, _ = index(lrows, li)
    nmap, d.duplicate_keys = index(nrows, ni)
    missing = sorted(set(lmap) - set(nmap), key=str)
    extra = sorted(set(nmap) - set(lmap), key=str)
    d.n_missing, d.n_extra = len(missing), len(extra)
    d.missing_keys = [shown(k, lmap, li) for k in missing[:sample]]
    d.extra_keys = [shown(k, nmap, ni) for k in extra[:sample]]
    for c in lcols:
        if c not in ni or c in script.key:
            continue
        for k in sorted(set(lmap) & set(nmap), key=str):
            a, b = lmap[k][li[c]], nmap[k][ni[c]]
            if _norm(a) != _norm(b):
                d.column_mismatches[c] = d.column_mismatches.get(c, 0) + 1
                if len(d.samples.setdefault(c, [])) < sample:
                    d.samples[c].append((shown(k, lmap, li), a, b))
    return d


def describe(d: Diff) -> str:
    if d.match:
        return f"MATCH: {d.table} reproduces the legacy output exactly ({d.legacy_rows} rows)."
    out = [f"MISMATCH: {d.table}: legacy {d.legacy_rows} rows, new {d.new_rows} rows"]
    if d.missing_columns:
        out.append(f"  columns missing from the new output: {d.missing_columns}")
    if d.extra_columns:
        out.append(f"  extra columns in the new output (not in legacy): {d.extra_columns}")
    if d.n_missing:
        out.append(f"  {d.n_missing} keys in legacy but not in new, e.g. {d.missing_keys}")
    if d.n_extra:
        out.append(f"  {d.n_extra} keys in new but not in legacy, e.g. {d.extra_keys}")
    if d.duplicate_keys:
        out.append(f"  {d.duplicate_keys} duplicate keys in the new output")
    for c, n in d.column_mismatches.items():
        ex = "; ".join(f"key {k}: legacy {a!r} vs new {b!r}" for k, a, b in d.samples.get(c, []))
        out.append(f"  column {c}: {n} rows differ, e.g. {ex}")
    return "\n".join(out)
