#!/usr/bin/env python3
"""Schedule maintenance tasks to technicians and days (OR-Tools CP-SAT).

Usage:
    python schedule_maintenance.py plan.json [--out schedule.json]

plan.json:
{
  "days": 5,
  "technicians": [{"id": "T1", "skills": ["hvac"], "hours_per_day": 8}],
  "tasks": [{"id": "WO-1", "asset": "AHU-03", "skill": "hvac", "hours": 3, "score": 90, "due_day": 1}]
}
`score` is the priority from the rules engine (criticality × cost × SLA). `due_day` is 0-based.
OR concepts: assignment + capacity (bin packing) + soft deadlines. Each task gets at most one (technician, day);
skills must match; hours per technician per day are limited; scheduling high-score tasks early is rewarded,
lateness past the due day is penalised; tasks that do not fit are reported, not dropped silently.
"""
import argparse, json
from pathlib import Path
from ortools.sat.python import cp_model

def schedule(plan, late_penalty=20):
    days, techs, tasks = plan["days"], plan["technicians"], plan["tasks"]
    m = cp_model.CpModel()
    x = {}
    for t in tasks:
        for k in techs:
            if t["skill"] in k["skills"]:
                for d in range(days):
                    x[t["id"], k["id"], d] = m.NewBoolVar(f"{t['id']}_{k['id']}_{d}")
    for t in tasks:
        m.Add(sum(v for (ti, _, _), v in x.items() if ti == t["id"]) <= 1)
    for k in techs:
        for d in range(days):
            m.Add(sum(int(round(t["hours"] * 10)) * x[t["id"], k["id"], d] for t in tasks if (t["id"], k["id"], d) in x)
                  <= int(k["hours_per_day"] * 10))
    obj = []
    for (ti, ki, d), v in x.items():
        t = next(t for t in tasks if t["id"] == ti)
        value = t["score"] * 10 - d  # earlier is slightly better
        late = max(0, d - t.get("due_day", days)) * late_penalty * 10
        obj.append((value - late) * v)
    m.Maximize(sum(obj))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 10
    status = s.Solve(m)
    out, done = [], set()
    for (ti, ki, d), v in x.items():
        if s.Value(v):
            t = next(t for t in tasks if t["id"] == ti)
            out.append({"task": ti, "asset": t["asset"], "technician": ki, "day": d, "hours": t["hours"], "score": t["score"],
                        "late_days": max(0, d - t.get("due_day", days))})
            done.add(ti)
    out.sort(key=lambda r: (r["day"], r["technician"]))
    return {"status": s.StatusName(status), "scheduled": out,
            "unscheduled": [t["id"] for t in tasks if t["id"] not in done],
            "utilisation": {k["id"]: round(sum(r["hours"] for r in out if r["technician"] == k["id"]) / (k["hours_per_day"] * days), 2) for k in techs}}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan_json"); ap.add_argument("--out", default="schedule.json")
    a = ap.parse_args()
    res = schedule(json.loads(Path(a.plan_json).read_text()))
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(res["status"])
    for r in res["scheduled"]:
        print(f"  day {r['day']}  {r['technician']:<4} {r['task']:<8} {r['asset']:<10} {r['hours']} h  score {r['score']}{'  LATE ' + str(r['late_days']) + ' d' if r['late_days'] else ''}")
    if res["unscheduled"]:
        print("  not scheduled:", ", ".join(res["unscheduled"]))
    print("  utilisation:", res["utilisation"], f"-> {a.out}")

if __name__ == "__main__":
    main()
