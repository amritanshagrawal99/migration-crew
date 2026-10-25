# migration-crew

[![CI](https://github.com/amritanshagrawal99/migration-crew/actions/workflows/ci.yml/badge.svg)](https://github.com/amritanshagrawal99/migration-crew/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**A crew of Claude agents that migrates a legacy Teradata ETL estate to DuckDB.** The crew converts every job, runs
it, reconciles its output against the legacy system's row by row, and fixes what differs. Each job is then graded on
**a dataset the agents never saw**, so a conversion that only patches the visible data fails.

Built on the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview): a lead agent, converter and
reviewer subagents, in-process MCP tools, structured output and a spend cap. Claude Opus 5.5 by default.

```mermaid
flowchart LR
    L[lead] -->|"wave 1 (parallel)"| C1[converter s1]
    L --> C2[converter s2]
    L --> C5[converter s5]
    L -->|after deps pass| C3[converter s3 ...]
    C1 & C2 & C5 & C3 --> T["auto_convert / save_target / run_target / reconcile<br/>query_source / query_legacy_output"]
    L -->|passing scripts| R[reviewer]
    R -->|changes_requested| L
    L --> REP[migration report]
    T -. dataset A only .-> A[(sources + legacy outputs A)]
    G[grader] -. after the run .-> B[(dataset B + legacy outputs B, hidden)]
```

## The estate

9 Teradata BTEQ scripts in a dependency graph, from staging (`s1`, `s2`, `s5`) to aggregates, a top-10 with ties,
churn flags and a type-2 dimension, plus [platform notes](estate/legacy/PLATFORM_NOTES.md). Each script hides
Teradata behaviour that DuckDB doesn't share:

| Trap | Where | What goes wrong in DuckDB |
|---|---|---|
| Session-mode comparison ignores case and trailing spaces | s1, s2, s5, s9 | `segment = 'gold'` misses `'Gold   '`; the padded-SKU join returns 0 of 2443 rows; the dimension sees 76 false changes |
| `RoundHalfwayMagUp = FALSE` (round half to even) | s3 | `CAST(... AS DECIMAL(14,1))` rounds 1615.85 to 1615.9 instead of 1615.8 |
| `ZEROIFNULL`, `TOP n WITH TIES` | s1, s7 | don't exist / don't parse |
| Integer division truncates; NULLs sort first | s3, s4 | the auto-converter (sqlglot) already handles these |

Without the agents, the auto-converter's output (sql-migration-accelerator on sqlglot) fails 6 of 9 scripts, and
the downstream scripts fail with them. A test checks this.

**How it's graded.**
- **Dataset A** (300 customers) is what the agents work with. They see its sources and the legacy outputs, but only
  through diffs and read-only queries.
- **Dataset B** (520 customers, another seed) is hidden from them. It also has spellings A doesn't, such as
  `'gOLD'`, `'sHIPPED'` and `'Sku0005'`.
- After the run, every saved conversion runs on both datasets and is reconciled with the legacy outputs. A
  conversion that matches A and fails B counts as **overfit**. A test shows that listing dataset A's spellings
  instead of implementing the rule is caught this way.
- The report's claimed status for every script is checked too.

## Results: crew vs one agent

Same model (Claude Opus 5.5, effort medium), same tools, same budget:

| Mode | Unseen dataset B | Overfit | Report claims correct | Review | Tool calls | Time | Estimated cost |
|---|---|---|---|---|---|---|---|
| **crew**: lead + converters + reviewer | **9 / 9** | 0 | 9 / 9 | 9 approved | 223 (20 delegations) | 266 s | $3.02 |
| **solo**: one agent | **9 / 9** | 0 | 9 / 9 | 9 approved | 68 | 177 s | $0.73 |

**At this size the crew buys nothing.** Both modes migrate every script, find every trap and generalize to the
unseen data. One agent does it in 2/3 of the time for 1/4 of the cost, because all nine scripts fit comfortably in
its context. The crew pays for every brief and handoff: each converter and reviewer starts from zero and re-reads the
legacy SQL and platform notes.

The crew's working style is visible in [`runs/published/crew`](runs/published/crew):
- **Waves.** It converted s1, s2 and s5 in parallel, then s3, s4 and s9 once their dependencies passed.
- **Verification.** The lead re-ran reconcile on every claimed pass.
- **Deep review.** The reviewer ran its own edge-case probes. It also noticed that a Teradata `GROUP BY` compares
  case-insensitively too, which no trap tests.

The interesting question is where that changes: an estate too big for one context window, where isolating each script
in its own agent should start to pay off. That experiment is the next step ([#1](../../issues/1)).

## Design

- **Parity, not correctness.** The agents must reproduce the legacy outputs exactly, including behaviour they think
  is wrong; suspected legacy bugs are recorded as notes. That is the actual job in a migration.
- **The data can't be gamed.**
  - The agents work on dataset A only. Dataset B and the reference SQL live in `grading/`, which no tool can reach.
  - Converted SQL runs in an in-memory DuckDB with external access disabled and the configuration locked. It can't
    read files, `ATTACH` the grading database, or `COPY` anything out, and a test checks all three.
  - Query tools take one `SELECT`, checked with sqlglot against an allowlist of tables.
- **Tools do the measuring.** `reconcile` compares by key and reports:
  - missing and extra keys, and duplicate keys;
  - per-column mismatch counts, with sample rows showing the legacy and new values.

  The model reads diffs, not raw tables.
- **The lead verifies, never trusts.** Subagent claims are re-checked with `reconcile`, and the report must take
  statuses from the workspace state. The grader checks them anyway.
- **Bounded.** A spend cap, turn caps per agent, a subagent depth of 1, at most 4 concurrent subagents, and no
  built-in Claude Code tools other than `Agent`.

## Run it

```bash
pip install git+https://github.com/amritanshagrawal99/migration-crew
migration-crew run --mode crew        # or --mode solo; then grades on both datasets
migration-crew grade runs/<workspace> # re-grade a finished run
migration-crew tool runs/x reconcile '{"script": "s5_order_lines_enriched"}'   # any tool, no model
```

Authenticate the Agent SDK with an `ANTHROPIC_API_KEY`, or with `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`.
`python estate/build.py` regenerates both datasets and the legacy outputs.

## Tests

`pytest` runs without a model:
- The reference passes both datasets.
- Auto-conversion fails where the traps are.
- A dataset-A-fitted conversion is flagged as overfit.
- False status claims are caught.
- The SQL sandbox holds against ATTACH, file reads and COPY.
- The query tools are read-only and scoped.
- Grading data never appears inside the estate.

## License

[MIT](LICENSE)
