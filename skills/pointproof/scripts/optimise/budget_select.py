#!/usr/bin/env python3
"""Choose which projects to fund within a budget (0/1 knapsack, OR-Tools CP-SAT).

Usage:
    python budget_select.py projects.csv --budget 2000000 [--objective saving|co2] [--out selection.json]

projects.csv columns: project, cost, annual_saving, co2_saving_t, group (optional; at most one project per group)
OR concepts: integer programming. One yes/no variable per project; maximise total benefit;
total cost ≤ budget; at most one project from each mutually exclusive group.
"""
import argparse, csv, json
from pathlib import Path
from ortools.sat.python import cp_model

def select(rows, budget, objective="saving"):
    key = "annual_saving" if objective == "saving" else "co2_saving_t"
    scale = 1 if objective == "saving" else 1000  # CP-SAT needs integers
    m = cp_model.CpModel()
    x = {r["project"]: m.NewBoolVar(r["project"]) for r in rows}
    m.Add(sum(int(round(float(r["cost"]))) * x[r["project"]] for r in rows) <= int(budget))
    groups = {}
    for r in rows:
        if r.get("group"):
            groups.setdefault(r["group"], []).append(x[r["project"]])
    for g in groups.values():
        m.Add(sum(g) <= 1)
    m.Maximize(sum(int(round(float(r[key]) * scale)) * x[r["project"]] for r in rows))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 10
    status = s.Solve(m)
    chosen = [r for r in rows if s.Value(x[r["project"]])]
    cost = sum(float(r["cost"]) for r in chosen); saving = sum(float(r["annual_saving"]) for r in chosen)
    return {"status": s.StatusName(status), "budget": budget, "objective": objective,
            "chosen": [r["project"] for r in chosen], "not_chosen": [r["project"] for r in rows if r not in chosen],
            "total_cost": cost, "annual_saving": saving, "co2_saving_t": sum(float(r["co2_saving_t"]) for r in chosen),
            "simple_payback_years": round(cost / saving, 1) if saving else None}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projects_csv"); ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--objective", choices=["saving", "co2"], default="saving"); ap.add_argument("--out", default="selection.json")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.projects_csv, newline="", encoding="utf-8-sig")))
    res = select(rows, a.budget, a.objective)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(f"{res['status']}: fund {', '.join(res['chosen'])}")
    print(f"cost {res['total_cost']:,.0f} of {a.budget:,.0f}; saving {res['annual_saving']:,.0f}/yr; CO2 {res['co2_saving_t']:,.0f} t/yr; payback {res['simple_payback_years']} yr")
    print(f"-> {a.out}")

if __name__ == "__main__":
    main()
