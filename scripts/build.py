"""Build the DuckDB warehouse from the raw CSVs and export the dashboard data.

    python scripts/build.py        → warehouse.duckdb + docs/data.json
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def to_py(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, date):
        return v.isoformat()
    return v


def rows(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [{c: to_py(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def main() -> None:
    db = ROOT / "warehouse.duckdb"
    db.unlink(missing_ok=True)
    con = duckdb.connect(str(db))
    import os
    os.chdir(ROOT)
    for f in sorted((ROOT / "sql").glob("*.sql")):
        con.execute(f.read_text(encoding="utf-8"))
        print(f"ran {f.name}")
    data = {
        "status_date": rows(con, "select max(status_month) as d from marts.project_status")[0]["d"],
        "projects": rows(con, "select * from marts.project_status order by project_code"),
        "scurve": rows(con, "select * from marts.evm_project_monthly order by project_code, month"),
        "planned": rows(con, """select project_code, month, sum(pv_month) over (partition by project_code order by month) as pv
                                from (select project_code, month, sum(planned_value_try) as pv_month
                                      from staging.planned_spend group by project_code, month)
                                order by project_code, month"""),
        "categories": rows(con, "select * from marts.category_variance order by project_code, cost_code"),
        "changes": rows(con, "select * from staging.change_orders order by raised_on desc"),
        "vendors": rows(con, "select * from marts.vendor_spend order by spend_try desc"),
    }
    out = ROOT / "docs" / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"exported {out.relative_to(ROOT)}")
    for p in data["projects"]:
        print(f"  {p['project_code']} {p['project_name'][:28]:28} CPI {p['cpi']:.2f}  SPI {p['spi']:.2f}  {p['health']}")


if __name__ == "__main__":
    main()
