"""Data tests on the built warehouse. Run `python scripts/build.py` first."""
from pathlib import Path

import duckdb
import pytest

DB = Path(__file__).resolve().parents[1] / "warehouse.duckdb"


@pytest.fixture(scope="module")
def con():
    if not DB.exists():
        pytest.skip("run scripts/build.py first")
    return duckdb.connect(str(DB), read_only=True)


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def test_earned_value_never_exceeds_budget(con):
    assert scalar(con, "select count(*) from marts.evm_category_monthly where ev > bac + 0.01") == 0


def test_cumulative_values_never_decrease(con):
    bad = scalar(con, """
        select count(*) from (
            select ac - lag(ac) over (partition by project_code order by month) as d_ac,
                   pv - lag(pv) over (partition by project_code order by month) as d_pv
            from marts.evm_project_monthly)
        where d_ac < -0.01 or d_pv < -0.01""")
    assert bad == 0


def test_actual_cost_reconciles_to_invoices(con):
    diff = scalar(con, """
        select abs((select sum(ac) from marts.project_status) - (select sum(amount_try) from staging.actual_costs))""")
    assert diff < 1


def test_budget_lines_sum_to_project_budget(con):
    assert scalar(con, """
        select count(*) from staging.projects p
        join (select project_code, sum(budget_try) b from staging.budget_lines group by 1) l using (project_code)
        where abs(p.budget_try - l.b) > 1""") == 0


def test_planned_value_reaches_budget_at_finish(con):
    assert scalar(con, """
        select count(*) from (select project_code, sum(planned_value_try) pv from staging.planned_spend group by 1) s
        join staging.projects p using (project_code) where abs(s.pv - p.budget_try) / p.budget_try > 0.001""") == 0


def test_indices_match_definitions(con):
    rows = con.execute("select ev, ac, pv, cpi, spi, bac, eac from marts.project_status").fetchall()
    for ev, ac, pv, cpi, spi, bac, eac in rows:
        assert abs(float(ev) / float(ac) - cpi) < 0.001
        assert abs(float(ev) / float(pv) - spi) < 0.001
        assert abs(float(bac) / cpi - float(eac)) / float(eac) < 0.001


def test_health_rules(con):
    for cpi, spi, health in con.execute("select cpi, spi, health from marts.project_status").fetchall():
        expected = "At risk" if cpi < 0.95 or spi < 0.90 else "Watch" if cpi < 1 or spi < 0.97 else "On track"
        assert health == expected
