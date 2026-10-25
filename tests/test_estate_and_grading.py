"""Deterministic tests (no model): the benchmark is sound before any agent touches it."""
import shutil

import pytest

from migration_crew.estate import ROOT, chain, scripts
from migration_crew.grading import grade
from migration_crew.tools import Workspace, call

REF = ROOT / "grading" / "reference"


def workspace(tmp_path, sql: dict[str, str]) -> Workspace:
    ws = Workspace(tmp_path / "ws")
    for name, text in sql.items():
        (ws.root / "target" / f"{name}.sql").write_text(text)
    return ws


def reference() -> dict[str, str]:
    return {n: (REF / f"{n}.sql").read_text() for n in scripts()}


def test_dependencies_are_derived_from_the_sql():
    s = scripts()
    assert s["s8_churn_flags"].depends_on == ["s1_stg_customers", "s3_customer_order_stats", "s4_first_fulfilment"]
    assert chain("s8_churn_flags").index("s2_stg_orders") < chain("s8_churn_flags").index("s3_customer_order_stats")


def test_reference_passes_both_datasets(tmp_path):
    g = grade(workspace(tmp_path, reference()).root, None)
    assert g["pass_a"] == g["pass_b"] == 9 and not g["overfit"]


def test_auto_conversion_alone_fails_where_the_traps_are(tmp_path):
    from sma.converter import convert_script, render_script
    legacy = ROOT / "estate" / "legacy"
    auto = {n: render_script(convert_script((legacy / f"{n}.sql").read_text(), "teradata", "duckdb"), "duckdb")
            for n in scripts()}
    g = grade(workspace(tmp_path, auto).root, None)
    failing = {r["script"] for r in g["rows"] if not r["a"]}
    # the traps live in s1, s2, s3, s5, s7, s9; s4, s6 and s8 fail too because they depend on them
    assert {"s1_stg_customers", "s2_stg_orders", "s3_customer_order_stats", "s5_order_lines_enriched",
            "s7_top_customers", "s9_dim_customer_scd2"} <= failing


def test_a_conversion_fitted_to_dataset_a_fails_dataset_b(tmp_path):
    """Listing dataset A's spellings instead of implementing Teradata's comparison rule passes A, fails B."""
    sql = reference()
    sql["s1_stg_customers"] = sql["s1_stg_customers"].replace(
        "WHEN upper(rtrim(segment)) = 'GOLD'", "WHEN segment IN ('Gold', 'GOLD', 'gold ', 'Gold   ')").replace(
        "WHEN upper(rtrim(segment)) = 'SILVER'", "WHEN segment IN ('Silver', 'silver', 'SILVER ')")
    g = grade(workspace(tmp_path, sql).root, None)
    assert "s1_stg_customers" in g["overfit"]


def test_report_claims_are_checked(tmp_path):
    sql = reference()
    del sql["s7_top_customers"]
    report = {"scripts": [{"script": "s7_top_customers", "status": "passing"}]}
    g = grade(workspace(tmp_path, sql).root, report)
    assert g["claims_honest"] == 8


@pytest.mark.parametrize("sql", ["ATTACH 'grading/golden_b.duckdb' AS g; CREATE TABLE stg_customers AS SELECT 1",
                                 "CREATE TABLE stg_customers AS SELECT * FROM read_csv('grading/reference/s1_stg_customers.sql')",
                                 "COPY customers TO 'leak.csv'; CREATE TABLE stg_customers AS SELECT 1"])
def test_converted_sql_cannot_reach_outside_its_sandbox(tmp_path, sql):
    ws = workspace(tmp_path, {"s1_stg_customers": sql})
    text, _ = call(ws, "run_target", {"script": "s1_stg_customers"})
    assert "ERROR" in text and ("Permission" in text or "disabled" in text.lower()), text


def test_query_tools_are_read_only_and_scoped(tmp_path):
    ws = workspace(tmp_path, {})
    assert call(ws, "query_source", {"sql": "DELETE FROM customers"})[1]
    assert call(ws, "query_source", {"sql": "SELECT * FROM stg_customers"})[1]          # not a source table
    assert call(ws, "query_legacy_output", {"sql": "SELECT * FROM customers"})[1]       # not an output table
    text, err = call(ws, "query_legacy_output", {"sql": "SELECT count(*) FROM top_customers"})
    assert not err and "28" in text


def test_save_target_requires_the_output_table(tmp_path):
    ws = workspace(tmp_path, {})
    text, err = call(ws, "save_target", {"script": "s1_stg_customers", "sql": "CREATE TABLE x AS SELECT 1"})
    assert err and "stg_customers" in text


def test_grading_data_is_not_in_the_estate():
    estate = {p.name for p in (ROOT / "estate").rglob("*")}
    assert "data_b.duckdb" not in estate and "golden_b.duckdb" not in estate
    assert not any("reference" in p.parts for p in (ROOT / "estate").rglob("*"))


def test_workspace_state_tracks_attempts(tmp_path):
    ws = workspace(tmp_path, {})
    call(ws, "save_target", {"script": "s2_stg_orders", "sql": "CREATE TABLE stg_orders AS SELECT * FROM orders"})
    call(ws, "save_target", {"script": "s2_stg_orders", "sql": "CREATE TABLE stg_orders AS SELECT * FROM orders"})
    assert ws.state()["s2_stg_orders"]["attempts"] == 2
    shutil.rmtree(ws.root)


def test_generated_estate_is_sound(tmp_path, monkeypatch):
    """A template-generated estate: the reference passes both datasets, auto-conversion fails every script with a
    trap and passes every control script, and dependent scripts read earlier outputs."""
    import json

    from sma.converter import convert_script, render_script

    from migration_crew.estate import legacy_dir
    from migration_crew.generator import write

    out = tmp_path / "n20"
    write(out, 20, seed=3)
    monkeypatch.setenv("MIGRATION_CREW_ESTATE", str(out / "estate"))
    s = scripts()
    assert len(s) == 20 and any(x.depends_on for x in s.values())
    assert not list((out / "estate").rglob("reference")) and not list((out / "estate").rglob("*_b.duckdb"))
    ref = {n: (out / "grading" / "reference" / f"{n}.sql").read_text() for n in s}
    g = grade(workspace(tmp_path / "ref", ref).root, None)
    assert g["pass_a"] == g["pass_b"] == 20
    auto = {n: render_script(convert_script((legacy_dir() / f"{n}.sql").read_text(), "teradata", "duckdb"), "duckdb")
            for n in s}
    g = grade(workspace(tmp_path / "auto", auto).root, None)
    traps = json.loads((out / "grading" / "manifest.json").read_text())["traps"]
    assert {r["script"] for r in g["rows"] if r["a"]} == {n for n in s if not traps[n]}


@pytest.mark.parametrize("mode", ["crew", "solo"])
def test_published_runs_still_grade_as_reported(mode, tmp_path):
    """The committed conversions keep passing on whichever DuckDB this CI job installed (1.5 on Python 3.10, 2.x
    elsewhere): parity proven on one engine version is not parity on another."""
    import json
    src = ROOT / "runs" / "published" / mode
    ws = tmp_path / mode
    shutil.copytree(src, ws)
    report = json.loads((src / "result.json").read_text())["run"]["report"]
    g = grade(Workspace(ws).root, report)
    assert g["pass_b"] == g["scripts"] == 9 and g["claims_honest"] == 9
