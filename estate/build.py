"""Build the hand-written estate's data: python estate/build.py

    estate/data_a.duckdb      source tables, dataset A (the agents can query these)
    estate/golden_a.duckdb    the legacy system's outputs on dataset A (the agents see only diffs against them)
    grading/data_b.duckdb     dataset B: another seed, more rows (hidden; final grading only)
    grading/golden_b.duckdb   legacy outputs on dataset B (hidden)

"Legacy outputs" are produced by grading/reference/*.sql: DuckDB SQL that reproduces the Teradata semantics of the
scripts in estate/legacy/ (session-mode string comparison, NULLs sorting first, INTEGER division, TOP WITH TIES).
Both datasets contain every pattern that makes those semantics matter, so the differences show up in dataset A, and
a conversion that only patches dataset A's numbers fails on dataset B. The generator lives in migration_crew.datagen;
`migration-crew generate` builds larger estates from templates with the same data.
"""
from __future__ import annotations

import re
from pathlib import Path

from migration_crew.datagen import generate, write_golden, write_sources

ROOT = Path(__file__).resolve().parent.parent
LEGACY = ROOT / "estate" / "legacy"
REFERENCE = ROOT / "grading" / "reference"
SCRIPTS = sorted(p.stem for p in LEGACY.glob("s*.sql"))


def output_of(script: str) -> str:
    return re.search(r"--\s*OUTPUT:\s*(\w+)", (LEGACY / f"{script}.sql").read_text()).group(1)


if __name__ == "__main__":
    reference = {s: (REFERENCE / f"{s}.sql").read_text() for s in SCRIPTS}
    outputs = {s: output_of(s) for s in SCRIPTS}
    for label, seed, n, data, gold in (("A", 11, 300, ROOT / "estate" / "data_a.duckdb", ROOT / "estate" / "golden_a.duckdb"),
                                       ("B", 29, 520, ROOT / "grading" / "data_b.duckdb", ROOT / "grading" / "golden_b.duckdb")):
        write_sources(data, generate(seed, n, extra=label == "B"))
        print(label, write_golden(data, gold, reference, outputs))
