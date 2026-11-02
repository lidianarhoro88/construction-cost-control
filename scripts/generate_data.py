"""Synthetic project-controls data for a fictional Istanbul construction contractor.

Six projects, each with a budget broken down by WBS cost category, a planned
monthly spend curve (S-curve), monthly progress reports (% complete per
category), actual costs booked from subcontractor and supplier invoices, and
approved change orders. A few projects are given realistic problems: steel price
escalation, a late foundation package, scope creep through change orders.
"""
import csv
import math
import random
from datetime import date
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
rnd = random.Random(42)
STATUS_DATE = date(2026, 10, 31)

PROJECTS = [
    # code, name, district, type, start, months, budget (TRY m), profile of trouble
    ("P-101", "Ataşehir Residential Tower", "Ataşehir", "Residential", date(2025, 9, 1), 26, 820, "steel"),
    ("P-102", "Pendik Logistics Warehouse", "Pendik", "Industrial", date(2026, 3, 1), 14, 310, "healthy"),
    ("P-103", "Başakşehir Hospital Annex", "Başakşehir", "Healthcare", date(2025, 5, 1), 30, 1450, "late"),
    ("P-104", "Kadıköy Office Refurbishment", "Kadıköy", "Commercial", date(2026, 4, 1), 12, 140, "scope"),
    ("P-105", "Esenyurt School Campus", "Esenyurt", "Education", date(2025, 11, 1), 20, 460, "healthy"),
    ("P-106", "Sarıyer Villa Complex", "Sarıyer", "Residential", date(2025, 7, 1), 24, 690, "efficient"),
]
CATEGORIES = [  # code, name, share of budget, when it happens (0-1 of schedule: start, end)
    ("01", "Site works & excavation", 0.07, 0.00, 0.20),
    ("02", "Foundations", 0.11, 0.08, 0.30),
    ("03", "Structural concrete & steel", 0.27, 0.20, 0.62),
    ("04", "Envelope & facade", 0.14, 0.45, 0.80),
    ("05", "MEP (mechanical, electrical, plumbing)", 0.21, 0.40, 0.92),
    ("06", "Interior finishes", 0.13, 0.62, 0.98),
    ("07", "Site overheads & management", 0.07, 0.00, 1.00),
]


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def s_curve(t: float) -> float:
    """Cumulative share of work done at time t (0-1): a logistic S-curve."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return (1 / (1 + math.exp(-10 * (t - 0.5))) - 1 / (1 + math.exp(5))) / (1 / (1 + math.exp(-5)) - 1 / (1 + math.exp(5)))


def write(name, header, rows):
    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {name}.csv {len(rows):>5} rows")


projects, budget, plan, progress, actuals, changes = [], [], [], [], [], []
inv = 0
for code, name, district, ptype, start, months, bac_m, trouble in PROJECTS:
    bac = bac_m * 1_000_000
    end = add_months(start, months)
    projects.append([code, name, district, ptype, start.isoformat(), end.isoformat(), bac])
    elapsed = min(months_between(start, STATUS_DATE) + 1, months)
    for cat, cname, share, c0, c1 in CATEGORIES:
        cat_budget = round(bac * share, 2)
        budget.append([code, cat, cname, cat_budget])
        # productivity factors: >1 means work done slower than planned / costs more
        cost_factor = 1.0 + rnd.uniform(-0.03, 0.04)
        if trouble == "steel" and cat == "03":
            cost_factor = 1.22
        if trouble == "scope" and cat in ("05", "06"):
            cost_factor = 1.12
        if trouble == "efficient":
            cost_factor = 0.95
        speed = (0.72 if cat in ("02", "03") else 0.84) if trouble == "late" else (1.04 if trouble == "efficient" else rnd.uniform(0.96, 1.02))
        for m in range(months):
            month = add_months(start, m)
            t_end = (m + 1) / months
            planned = s_curve((t_end - c0) / (c1 - c0)) if c1 > c0 else 1.0
            prev = s_curve((m / months - c0) / (c1 - c0)) if m else 0.0
            plan.append([code, cat, month.isoformat(), round(cat_budget * (planned - prev), 2)])
            if m < elapsed:
                pct = min(1.0, s_curve(((t_end * speed) - c0) / (c1 - c0)))
                prev_pct = min(1.0, s_curve(((m / months * speed) - c0) / (c1 - c0))) if m else 0.0
                progress.append([code, cat, month.isoformat(), round(pct * 100, 1)])
                spend = cat_budget * (pct - prev_pct) * cost_factor
                if spend > 0:
                    # spend arrives as 1-3 invoices per month
                    parts = rnd.randint(1, 3)
                    for k in range(parts):
                        inv += 1
                        vendor = rnd.choice(["Boğaziçi Beton", "Marmara Çelik", "Anadolu Elektrik", "Haliç Mekanik",
                                             "Kuzey Cephe", "Yıldız İç Mimari", "Kendi ekip (payroll)"])
                        actuals.append([f"INV-{inv:06d}", code, cat, add_months(month, 0).replace(day=rnd.randint(5, 27)).isoformat(),
                                        vendor, round(spend / parts * rnd.uniform(0.9, 1.1), 2)])
    # change orders
    n_co = {"scope": 9, "late": 4}.get(trouble, rnd.randint(1, 3))
    for k in range(n_co):
        cat = rnd.choice(["04", "05", "06"]) if trouble == "scope" else rnd.choice([c[0] for c in CATEGORIES])
        status = rnd.choices(["Approved", "Pending", "Rejected"], [6, 3, 1])[0]
        amount = round(bac * rnd.uniform(0.004, 0.018) * (1.8 if trouble == "scope" else 1), 2)
        raised = add_months(start, rnd.randint(1, max(1, elapsed - 1))).replace(day=rnd.randint(1, 27))
        changes.append([f"CO-{code[-3:]}-{k + 1:02d}", code, cat, raised.isoformat(), status, amount,
                        rnd.choice(["Client design change", "Unforeseen ground conditions", "Material substitution",
                                    "Regulatory requirement", "Additional MEP scope"])])

print(f"Status date {STATUS_DATE} → {RAW}")
write("projects", ["project_code", "project_name", "district", "project_type", "start_date", "planned_finish", "budget_try"], projects)
write("budget_lines", ["project_code", "cost_code", "cost_category", "budget_try"], budget)
write("planned_spend", ["project_code", "cost_code", "month", "planned_value_try"], plan)
write("progress", ["project_code", "cost_code", "month", "pct_complete"], progress)
write("actual_costs", ["invoice_id", "project_code", "cost_code", "invoice_date", "vendor", "amount_try"], actuals)
write("change_orders", ["change_order_id", "project_code", "cost_code", "raised_on", "status", "amount_try", "reason"], changes)
