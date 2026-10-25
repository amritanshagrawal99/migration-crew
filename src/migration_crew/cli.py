"""migration-crew command line."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path


def _table(g: dict) -> str:
    out = ["script | dataset A | dataset B (unseen) | claimed | review"]
    for r in g["rows"]:
        out.append(f"{r['script']} | {'PASS' if r['a'] else 'fail: ' + r['detail_a']} | "
                   f"{'PASS' if r['b'] else 'fail: ' + r['detail_b']} | {r['claimed'] or '-'} | {r['review'] or '-'}")
    out.append(f"\npassing on A {g['pass_a']}/{g['scripts']}, on unseen B {g['pass_b']}/{g['scripts']}, overfit {g['overfit'] or 'none'}, "
               f"report claims correct {g['claims_honest']}/{g['scripts']}, approved {g['approved']}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="migration-crew", description="Migrate a Teradata ETL estate to DuckDB with a crew of agents.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a migration, then grade it on both datasets")
    r.add_argument("--mode", choices=["crew", "solo"], default="crew")
    r.add_argument("--workspace", help="default: runs/<timestamp>-<mode>")
    r.add_argument("--model", default=None)
    r.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    r.add_argument("--budget", type=float, default=25.0, help="spend cap in USD for the whole run")
    r.add_argument("--quiet", action="store_true")
    g = sub.add_parser("grade", help="grade a finished workspace")
    g.add_argument("workspace")
    t = sub.add_parser("tool", help="call one crew tool directly (no model)")
    t.add_argument("workspace")
    t.add_argument("name")
    t.add_argument("args", nargs="?", default="{}")
    a = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    if a.cmd == "tool":
        from .tools import Workspace, call
        text, err = call(Workspace(Path(a.workspace)), a.name, json.loads(a.args))
        print(text)
        return 1 if err else 0

    from .grading import grade
    if a.cmd == "grade":
        report_file = Path(a.workspace) / "result.json"
        report = json.loads(report_file.read_text())["report"] if report_file.exists() else None
        print(_table(grade(a.workspace, report)))
        return 0

    from .agents import MODEL, migrate
    ws = Path(a.workspace or f"runs/{time.strftime('%Y%m%d-%H%M%S')}-{a.mode}")
    res = asyncio.run(migrate(ws, a.mode, a.model or MODEL, a.budget, a.effort,
                              None if a.quiet else (lambda line: print(line, flush=True))))
    gr = grade(ws, res.report)
    (ws / "result.json").write_text(json.dumps({"run": res.__dict__, "grade": gr}, indent=2, default=str), encoding="utf-8")
    print("\n" + _table(gr))
    print(f"\n{res.mode}: {res.turns} turns, {sum(res.tool_calls.values())} tool calls, {len(res.delegations)} delegations, "
          f"{res.seconds:.0f} s, ${res.cost_usd or 0:.2f} estimated" + (f"; ended with: {res.error}" if res.error else ""))
    return 0 if gr["pass_b"] == gr["scripts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
