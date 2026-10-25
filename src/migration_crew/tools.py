"""The crew's tools, bound to one run's workspace. All of them are confined to the estate and the workspace:

    workspace/target/<script>.sql   converted SQL, one file per legacy script (written only through save_target)
    workspace/state.json            per-script attempts, last reconcile result, review verdict, notes

Reads: the legacy scripts, the platform notes, dataset A's source tables and the legacy outputs on dataset A. Dataset
B and the reference SQL (grading/) are never reachable: queries run on in-memory copies with external access off.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from .estate import ScriptError, describe, estate_dir, legacy_dir, load, reconcile, run_chain, scripts

MAX_ROWS = 40


def DATA_A() -> Path:  # noqa: N802 - kept as a "constant" name; the estate is a run setting
    return estate_dir() / "data_a.duckdb"


def GOLDEN_A() -> Path:  # noqa: N802
    return estate_dir() / "golden_a.duckdb"


class ToolError(Exception):
    pass


@dataclass
class Workspace:
    root: Path
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        (self.root / "target").mkdir(parents=True, exist_ok=True)
        marker = self.root / "estate.txt"           # the estate this workspace belongs to (used by grading)
        if not marker.exists():
            marker.write_text(str(estate_dir()))
        if not self.state_path.exists():
            self.save_state({n: {"attempts": 0, "reconciles": 0, "status": "not_started", "review": None, "notes": []}
                             for n in scripts()})

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def save_state(self, st: dict) -> None:
        self.state_path.write_text(json.dumps(st, indent=2, default=str))

    def update(self, script: str, **kw) -> None:
        with self.lock:
            st = self.state()
            st[script].update(kw)
            self.save_state(st)

    def bump(self, script: str, key: str) -> int:
        with self.lock:
            st = self.state()
            st[script][key] += 1
            self.save_state(st)
            return st[script][key]

    def target_sql(self, script: str) -> str | None:
        p = self.root / "target" / f"{script}.sql"
        return p.read_text() if p.exists() else None


def _script(name: str):
    s = scripts()
    if name not in s:
        raise ToolError(f"no legacy script {name!r}; scripts: {', '.join(s)}")
    return s[name]


def _select_only(sql: str, allowed: set[str]) -> str:
    import sqlglot
    from sqlglot import exp
    try:
        stmts = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise ToolError(f"does not parse: {str(e)[:300]}") from None
    if len(stmts) != 1 or not isinstance(stmts[0], (exp.Select, exp.Union, exp.Except, exp.Intersect)):
        raise ToolError("only one read-only SELECT is allowed here")
    ctes = {c.alias for c in stmts[0].find_all(exp.CTE)}
    unknown = {t.name for t in stmts[0].find_all(exp.Table)} - allowed - ctes
    if unknown:
        raise ToolError(f"unknown tables {sorted(unknown)}; available: {sorted(allowed)}")
    return sql


def _rows(con, sql: str) -> str:
    try:
        cur = con.execute(sql)
    except duckdb.Error as e:
        raise ToolError(f"query failed: {str(e)[:400]}") from None
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(MAX_ROWS + 1)
    body = "\n".join(" | ".join("NULL" if v is None else repr(v) if isinstance(v, str) else str(v) for v in r)
                     for r in rows[:MAX_ROWS])
    more = f"\n(first {MAX_ROWS} rows; aggregate or filter for more)" if len(rows) > MAX_ROWS else ""
    return " | ".join(cols) + "\n" + body + more


# ------------------------------------------------------------------ tools

def inventory(ws: Workspace, args: dict) -> str:
    st = ws.state()
    lines = ["script | output table | key | depends on | status | attempts | review"]
    for n, s in scripts().items():
        x = st[n]
        lines.append(f"{n} | {s.output} | {', '.join(s.key)} | {', '.join(s.depends_on) or '-'} | {x['status']} | "
                     f"{x['attempts']} | {x['review'] or '-'}")
    srcs = sorted(t for s in scripts().values() for t in s.reads if t not in {x.output for x in scripts().values()})
    return "\n".join(lines) + f"\n\nsource tables: {', '.join(dict.fromkeys(srcs))}"


def platform_notes(ws: Workspace, args: dict) -> str:
    return (legacy_dir() / "PLATFORM_NOTES.md").read_text()


def read_legacy(ws: Workspace, args: dict) -> str:
    s = _script(args["script"])
    return (legacy_dir() / f"{s.name}.sql").read_text()


def auto_convert(ws: Workspace, args: dict) -> str:
    from sma.converter import convert_script, render_script
    s = _script(args["script"])
    res = convert_script((legacy_dir() / f"{s.name}.sql").read_text(), "teradata", "duckdb", path=f"{s.name}.sql")
    issues = [f"  {i.code} {i.severity.value}: {i.message}" for st in res.statements for i in st.issues]
    return ("Draft from sql-migration-accelerator (syntax only: it does not know this platform's runtime semantics). "
            "Not saved.\n\n" + render_script(res, "duckdb") + ("\nconverter notes:\n" + "\n".join(issues) if issues else ""))


def query_source(ws: Workspace, args: dict) -> str:
    srcs = {t for s in scripts().values() for t in s.reads} - {s.output for s in scripts().values()}
    sql = _select_only(args["sql"], srcs)
    return _rows(load(DATA_A()), sql)


def query_legacy_output(ws: Workspace, args: dict) -> str:
    outs = {s.output for s in scripts().values()}
    sql = _select_only(args["sql"], outs)
    con = load(GOLDEN_A())
    return "Legacy system's output on dataset A:\n" + _rows(con, sql)


def save_target(ws: Workspace, args: dict) -> str:
    import sqlglot
    s = _script(args["script"])
    sql = args["sql"]
    try:
        sqlglot.parse(sql, read="duckdb")
    except sqlglot.errors.ParseError as e:
        raise ToolError(f"not saved, the SQL does not parse as DuckDB: {str(e)[:300]}") from None
    if s.output.lower() not in sql.lower():
        raise ToolError(f"not saved: the SQL must create the output table {s.output}")
    (ws.root / "target" / f"{s.name}.sql").write_text(sql)
    n = ws.bump(s.name, "attempts")
    ws.update(s.name, status="saved")
    return f"saved {s.name} (version {n}). Run run_target or reconcile next."


def read_target(ws: Workspace, args: dict) -> str:
    s = _script(args["script"])
    sql = ws.target_sql(s.name)
    return sql if sql else f"{s.name} has no converted SQL yet."


def run_target(ws: Workspace, args: dict) -> str:
    s = _script(args["script"])
    try:
        con = run_chain(s.name, DATA_A(), ws.target_sql)
    except ScriptError as e:
        ws.update(s.name, status="error")
        return f"ERROR in {e.script}: {e.message}"
    cols = con.execute(f'DESCRIBE "{s.output}"').fetchall()
    n = con.execute(f'SELECT count(*) FROM "{s.output}"').fetchone()[0]
    return f"ran {s.name} and its dependencies on dataset A: {s.output} has {n} rows; columns: " + \
        ", ".join(f"{c[0]} {c[1]}" for c in cols)


def reconcile_tool(ws: Workspace, args: dict) -> str:
    s = _script(args["script"])
    ws.bump(s.name, "reconciles")
    try:
        con = run_chain(s.name, DATA_A(), ws.target_sql)
    except ScriptError as e:
        ws.update(s.name, status="error")
        return f"ERROR in {e.script}: {e.message}"
    golden = duckdb.connect(str(GOLDEN_A()), read_only=True)
    try:
        d = reconcile(s, golden, s.output, con)
    finally:
        golden.close()
    ws.update(s.name, status="passing" if d.match else "failing")
    dep_note = ""
    if not d.match and s.depends_on:
        dep_note = (f"\n(dependencies {', '.join(s.depends_on)} ran from their saved conversions: a difference can "
                    "come from them; reconcile them first)")
    return describe(d) + dep_note


def note(ws: Workspace, args: dict) -> str:
    s = _script(args["script"])
    kind = args.get("kind", "decision")
    with ws.lock:
        st = ws.state()
        st[s.name]["notes"].append({"kind": kind, "text": args["text"][:600]})
        ws.save_state(st)
    return f"noted ({kind}) on {s.name}"


def record_review(ws: Workspace, args: dict) -> str:
    s = _script(args["script"])
    verdict = args["verdict"]
    if verdict not in ("approved", "changes_requested"):
        raise ToolError("verdict must be approved or changes_requested")
    ws.update(s.name, review=verdict)
    with ws.lock:
        st = ws.state()
        st[s.name]["notes"].append({"kind": f"review:{verdict}", "text": args.get("comments", "")[:1200]})
        ws.save_state(st)
    return f"review of {s.name}: {verdict}"


S = {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]}
TOOLS = {
    "inventory": (inventory, "The migration plan: every legacy script with its output table, key, dependencies, and "
                  "current status, attempts and review verdict.", {}),
    "platform_notes": (platform_notes, "Notes about the legacy Teradata platform and the target.", {}),
    "read_legacy": (read_legacy, "The legacy Teradata SQL of one script.", S),
    "auto_convert": (auto_convert, "Draft a DuckDB conversion of one script with sql-migration-accelerator "
                     "(syntax only). Does not save it.", S),
    "query_source": (query_source, "Run one read-only SELECT on dataset A's source tables (max 40 rows).",
                     {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}),
    "query_legacy_output": (query_legacy_output, "Run one read-only SELECT on the legacy system's OUTPUT tables for "
                            "dataset A (what the migrated jobs must reproduce).",
                            {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}),
    "save_target": (save_target, "Save the DuckDB SQL for one script (replaces the previous version). The SQL must "
                    "create the script's output table; it may be several statements.",
                    {"type": "object", "properties": {"script": {"type": "string"}, "sql": {"type": "string"}},
                     "required": ["script", "sql"]}),
    "read_target": (read_target, "The currently saved DuckDB SQL of one script.", S),
    "run_target": (run_target, "Run one script's saved SQL (and its dependencies' saved SQL) on dataset A. Reports "
                   "errors or the output's row count and columns.", S),
    "reconcile": (reconcile_tool, "Run one script on dataset A and compare its output with the legacy output, by key: "
                  "row counts, missing/extra keys, and per-column differences with examples. Sets the status.", S),
    "note": (note, "Record a note on a script for the migration report: kind is trap, decision, legacy_bug or risk.",
             {"type": "object", "properties": {"script": {"type": "string"}, "kind": {"type": "string",
              "enum": ["trap", "decision", "legacy_bug", "risk"]}, "text": {"type": "string"}},
              "required": ["script", "kind", "text"]}),
    "record_review": (record_review, "Record a code-review verdict on a script: approved or changes_requested, with "
                      "comments the converter can act on.",
                      {"type": "object", "properties": {"script": {"type": "string"}, "verdict": {"type": "string",
                       "enum": ["approved", "changes_requested"]}, "comments": {"type": "string"}},
                       "required": ["script", "verdict"]}),
}


def call(ws: Workspace, name: str, args: dict) -> tuple[str, bool]:
    try:
        return TOOLS[name][0](ws, args or {}), False
    except ToolError as e:
        return f"error: {e}", True
    except KeyError as e:
        return f"error: missing argument {e}", True
