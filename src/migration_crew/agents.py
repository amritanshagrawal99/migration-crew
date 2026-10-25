"""The migration crew, on the Claude Agent SDK.

    lead        plans the migration in dependency order, runs converters in parallel waves, verifies their claims
                with reconcile, sends passing scripts to review, re-dispatches on review feedback, writes the report
    converter   owns one legacy script: draft -> save -> run -> reconcile -> fix, until it matches the legacy output
    reviewer    reads a passing conversion against the legacy SQL and the platform notes: rejects logic that only
                fits dataset A (literal values from the data, rules applied to some comparisons but not others)

`mode="solo"` runs one agent with the same tools and no subagents, as a baseline for the same budget.
All tools are in-process MCP tools bound to one workspace (tools.py); Claude Code's built-in tools are removed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .estate import scripts
from .tools import TOOLS, Workspace, call

MODEL = "claude-opus-5-5"

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "scripts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "script": {"type": "string"},
                    "status": {"type": "string", "enum": ["passing", "failing", "not_converted"]},
                    "traps": {"type": "array", "items": {"type": "string"},
                              "description": "Legacy semantics that differ in DuckDB and how the conversion handles them"},
                    "suspected_legacy_bugs": {"type": "array", "items": {"type": "string"}},
                    "review": {"type": "string", "enum": ["approved", "changes_requested", "not_reviewed"]},
                },
                "required": ["script", "status", "traps", "review"],
            },
        },
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "scripts", "risks"],
}

SEMANTICS = ("The goal is parity: reproduce the legacy outputs exactly, including legacy behaviour you think is "
             "wrong (record it as a legacy_bug note instead of fixing it). Implement the legacy platform's semantics "
             "as general rules (read platform_notes), applied to every comparison they affect, not only the ones "
             "dataset A happens to exercise: the migrated jobs will run on other data. Never hard-code values, keys "
             "or spellings taken from the data.")

CONVERTER_PROMPT = f"""You migrate one legacy Teradata script to DuckDB. Read it, read platform_notes, draft with \
auto_convert, save with save_target, then reconcile against the legacy output and fix what differs, until it \
matches. A difference can come from a dependency: if reconcile says so, report it rather than compensating for it. \
Record each trap you handle (a legacy semantic that differs in DuckDB) with note kind=trap. {SEMANTICS} When done, \
report the status, the traps, and anything you could not resolve."""

REVIEWER_PROMPT = f"""You review DuckDB conversions of legacy Teradata scripts before they are signed off. For the \
script you are given, read the legacy SQL, platform_notes and the saved conversion. Passing reconcile on dataset A \
is necessary but not sufficient. Reject a conversion that: hard-codes values, keys or spellings from the data; \
applies a semantic rule (case, trailing spaces, NULL order, rounding, integer division) to some comparisons but not \
to every one the rule affects; or depends on row order or data quirks. Use query_source to check how general the \
data really is. Record your verdict with record_review, with comments a converter can act on. {SEMANTICS}"""

LEAD_PROMPT = f"""You lead the migration of a Teradata ETL estate to DuckDB. Start with inventory and \
platform_notes. Convert scripts in dependency order: a script can only be reconciled once its dependencies are \
saved. Delegate each script to a converter subagent with a self-contained brief (the script name, its dependencies, \
and any traps already found in related scripts); run independent scripts in parallel and wait for their reports. \
Verify every claimed pass yourself with reconcile. Send each passing script to the reviewer; if it requests \
changes, give the converter the comments and have it fix and re-reconcile. Finish when every script passes and is \
approved, or when you cannot make progress. {SEMANTICS} The report must reflect the real status from inventory, not \
what the subagents claimed."""

SOLO_PROMPT = f"""You migrate a Teradata ETL estate to DuckDB on your own. Start with inventory and platform_notes, \
then convert every script in dependency order: read it, draft with auto_convert, save, reconcile against the legacy \
output, and fix differences until it matches. A difference can come from a dependency. Record each trap with note. \
Before finishing, review each passing conversion for rules applied only where dataset A exposed them. {SEMANTICS} \
The report must reflect the real status from inventory."""

CONVERTER_TOOLS = ["platform_notes", "read_legacy", "auto_convert", "query_source", "query_legacy_output",
                   "save_target", "read_target", "run_target", "reconcile", "note", "inventory"]
REVIEWER_TOOLS = ["platform_notes", "read_legacy", "read_target", "query_source", "query_legacy_output",
                  "record_review", "note", "inventory"]
LEAD_TOOLS = ["inventory", "platform_notes", "read_legacy", "read_target", "reconcile"]
SOLO_TOOLS = sorted(set(CONVERTER_TOOLS) | {"record_review"})


@dataclass
class RunResult:
    mode: str
    workspace: str
    report: dict | None = None
    error: str | None = None
    turns: int = 0
    cost_usd: float | None = None
    seconds: float = 0.0
    tool_calls: dict[str, int] = field(default_factory=dict)
    delegations: list[str] = field(default_factory=list)
    transcript: list[str] = field(default_factory=list)


def _server(ws: Workspace, counter: dict):
    import asyncio

    from claude_agent_sdk import create_sdk_mcp_server, tool

    def make(name, desc, schema):
        @tool(name, desc, schema or {"type": "object", "properties": {}})
        async def handler(args):
            counter[name] = counter.get(name, 0) + 1
            text, err = await asyncio.to_thread(call, ws, name, args)
            return {"content": [{"type": "text", "text": text}], **({"is_error": True} if err else {})}
        return handler

    return create_sdk_mcp_server(name="mig", version="0.1.0", tools=[make(n, d, s) for n, (_, d, s) in TOOLS.items()])


def _mcp(names):
    return [f"mcp__mig__{n}" for n in names]


def options(ws: Workspace, mode: str, counter: dict, model: str, budget_usd: float, effort: str):
    from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions

    common = dict(model=model, effort=effort, mcp_servers={"mig": _server(ws, counter)},
                  output_format={"type": "json_schema", "schema": REPORT_SCHEMA}, setting_sources=[],
                  cwd=str(ws.root), max_budget_usd=budget_usd,
                  env={"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1", "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
                       "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "4"})
    n = len(scripts())                              # turn caps grow with the estate
    if mode == "solo":
        return ClaudeAgentOptions(system_prompt=SOLO_PROMPT, tools=[], allowed_tools=_mcp(SOLO_TOOLS),
                                  max_turns=max(250, 10 * n), **common)
    return ClaudeAgentOptions(
        system_prompt=LEAD_PROMPT, tools=["Agent"],
        # permission is session-wide: every tool any subagent uses must be approved here
        allowed_tools=["Agent", *_mcp(sorted(set(LEAD_TOOLS) | set(CONVERTER_TOOLS) | set(REVIEWER_TOOLS)))],
        disallowed_tools=["Agent(fork)", "Agent(general-purpose)"],
        agents={
            "converter": AgentDefinition(description="Migrates ONE legacy Teradata script to DuckDB until it reconciles.",
                                         prompt=CONVERTER_PROMPT, tools=_mcp(CONVERTER_TOOLS), model="inherit", maxTurns=60),
            "reviewer": AgentDefinition(description="Reviews a passing conversion for generality before sign-off.",
                                        prompt=REVIEWER_PROMPT, tools=_mcp(REVIEWER_TOOLS), model="inherit", maxTurns=30),
        },
        max_turns=max(150, 6 * n), **common)


async def migrate(workspace: str | Path, mode: str = "crew", model: str = MODEL, budget_usd: float = 25.0,
                  effort: str = "medium", on_event=None) -> RunResult:
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock, query

    ws = Workspace(Path(workspace))
    res = RunResult(mode, str(workspace))
    counter: dict[str, int] = {}
    start = time.monotonic()
    prompt = "Migrate the estate to DuckDB, then write the migration report."
    try:
        async for m in query(prompt=prompt, options=options(ws, mode, counter, model, budget_usd, effort)):
            if isinstance(m, AssistantMessage):
                who = "sub" if getattr(m, "parent_tool_use_id", None) else "lead"
                for b in m.content:
                    if isinstance(b, ToolUseBlock) and b.name in ("Agent", "Task"):
                        brief = str(b.input.get("prompt", ""))[:120].replace("\n", " ")
                        res.delegations.append(f"{b.input.get('subagent_type')}: {brief}")
                        line = f"[{who}] -> {b.input.get('subagent_type')}: {brief}"
                    elif isinstance(b, ToolUseBlock):
                        arg = b.input.get("script") or (str(b.input.get("sql", ""))[:60].replace("\n", " ")) or ""
                        line = f"[{who}] {b.name.removeprefix('mcp__mig__')}({arg})"
                    elif isinstance(b, TextBlock) and b.text.strip():
                        line = f"[{who}] {b.text.strip()[:200]}"
                    else:
                        continue
                    res.transcript.append(line)
                    if on_event:
                        on_event(line)
            elif isinstance(m, ResultMessage):
                res.turns, res.cost_usd = m.num_turns, m.total_cost_usd
                if m.subtype == "success" and m.structured_output:
                    res.report, res.error = m.structured_output, None
                elif res.report is None:           # a later empty result must not mask an earlier report
                    res.error = f"{m.subtype}: {m.errors or m.result}"
                    if "Not logged in" in str(m.result) or "/login" in str(m.result):
                        raise RuntimeError("Claude Code is not authenticated: set ANTHROPIC_API_KEY, or "
                                           "CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`")
    except Exception as e:  # noqa: BLE001 - a failed run is still graded on what it saved
        res.error = res.error or f"{type(e).__name__}: {e}"
    res.seconds = round(time.monotonic() - start, 1)
    res.tool_calls = counter
    return res
