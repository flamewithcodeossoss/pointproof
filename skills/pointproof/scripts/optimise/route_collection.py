#!/usr/bin/env python3
"""Plan tomorrow's bin collection routes from fill levels (OR-Tools routing, capacitated VRP).

Usage:
    python route_collection.py bins.csv --vehicles 2 --vehicle-capacity 6000 [--threshold 80] [--out routes.json]

bins.csv columns: bin, x_m, y_m, capacity_l, fill_pct, fill_rate_pct_per_day   (first row with bin=DEPOT is the depot)
Step 1 (statistics): a bin is due if fill_pct + fill_rate_pct_per_day ≥ threshold, i.e. it will pass the threshold by tomorrow.
Step 2 (optimisation): visit every due bin once, each truck within its capacity (litres collected), minimising total distance.
OR concepts: capacitated vehicle routing problem (CVRP).
"""
import argparse, csv, json, math
from pathlib import Path
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

def plan(rows, vehicles, capacity, threshold=80):
    depot = next(r for r in rows if r["bin"].upper() == "DEPOT")
    due = [r for r in rows if r is not depot and float(r["fill_pct"]) + float(r["fill_rate_pct_per_day"]) >= threshold]
    skip = [r["bin"] for r in rows if r is not depot and r not in due]
    nodes = [depot] + due
    load = [0] + [int(float(r["capacity_l"]) * min(100.0, float(r["fill_pct"]) + float(r["fill_rate_pct_per_day"])) / 100) for r in due]
    dist = [[int(math.hypot(float(a["x_m"]) - float(b["x_m"]), float(a["y_m"]) - float(b["y_m"]))) for b in nodes] for a in nodes]
    if not due:
        return {"status": "nothing due", "routes": [], "skipped": skip}
    mgr = pywrapcp.RoutingIndexManager(len(nodes), vehicles, 0)
    rt = pywrapcp.RoutingModel(mgr)
    cb = rt.RegisterTransitCallback(lambda i, j: dist[mgr.IndexToNode(i)][mgr.IndexToNode(j)])
    rt.SetArcCostEvaluatorOfAllVehicles(cb)
    dcb = rt.RegisterUnaryTransitCallback(lambda i: load[mgr.IndexToNode(i)])
    rt.AddDimensionWithVehicleCapacity(dcb, 0, [capacity] * vehicles, True, "Load")
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.seconds = 5
    sol = rt.SolveWithParameters(p)
    if not sol:
        return {"status": "no solution (add vehicles or capacity)", "routes": [], "skipped": skip}
    routes, total = [], 0
    for v in range(vehicles):
        i, stops, d, l = rt.Start(v), [], 0, 0
        while not rt.IsEnd(i):
            n = mgr.IndexToNode(i)
            if n: stops.append(nodes[n]["bin"]); l += load[n]
            j = sol.Value(rt.NextVar(i)); d += dist[n][mgr.IndexToNode(j)]; i = j
        if stops:
            routes.append({"vehicle": v + 1, "stops": stops, "distance_m": d, "load_l": l}); total += d
    return {"status": "ok", "due_bins": len(due), "skipped": skip, "routes": routes, "total_distance_m": total}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bins_csv"); ap.add_argument("--vehicles", type=int, default=2); ap.add_argument("--vehicle-capacity", type=int, default=6000)
    ap.add_argument("--threshold", type=float, default=80); ap.add_argument("--out", default="routes.json")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.bins_csv, newline="", encoding="utf-8-sig")))
    res = plan(rows, a.vehicles, a.vehicle_capacity, a.threshold)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(f"{res['status']}: {res.get('due_bins', 0)} bins due, {len(res['skipped'])} skipped")
    for r in res["routes"]:
        print(f"  truck {r['vehicle']}: DEPOT → {' → '.join(r['stops'])} → DEPOT  ({r['distance_m']} m, {r['load_l']} L)")
    print(f"-> {a.out}")

if __name__ == "__main__":
    main()
