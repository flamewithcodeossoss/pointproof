#!/usr/bin/env python3
"""Reorder point, safety stock and economic order quantity (EOQ) per item.

Usage:
    python reorder.py items.csv [--service-level 0.95] [--out reorder.json]

items.csv columns: item, daily_demand, daily_demand_std, lead_time_days, order_cost, holding_cost_per_unit_year
  daily_demand        average units used per day (from consumption history or occupancy × usage rate)
  daily_demand_std    standard deviation of daily use
OR concepts: inventory theory — (s, Q) policy. Safety stock = z × σ × √L; reorder point = d × L + safety stock;
EOQ = √(2 × annual demand × order cost ÷ holding cost).
"""
import argparse, csv, json, math
from pathlib import Path
from statistics import NormalDist

def plan(rows, service_level=0.95):
    z = NormalDist().inv_cdf(service_level)
    out = []
    for r in rows:
        d, sd, L = float(r["daily_demand"]), float(r["daily_demand_std"]), float(r["lead_time_days"])
        S, H = float(r["order_cost"]), float(r["holding_cost_per_unit_year"])
        ss = z * sd * math.sqrt(L)
        rop = d * L + ss
        eoq = math.sqrt(2 * d * 365 * S / H) if H > 0 else None
        out.append({"item": r["item"], "reorder_point": math.ceil(rop), "safety_stock": math.ceil(ss),
                    "order_quantity": math.ceil(eoq) if eoq else None,
                    "orders_per_year": round(d * 365 / eoq, 1) if eoq else None,
                    "why": f"Lead-time demand {d * L:.0f} + safety stock {ss:.0f} (z={z:.2f} for {service_level:.0%} service)"})
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("items_csv"); ap.add_argument("--service-level", type=float, default=0.95); ap.add_argument("--out", default="reorder.json")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.items_csv, newline="", encoding="utf-8-sig")))
    res = plan(rows, a.service_level)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(f"{'item':<24} {'reorder at':>10} {'safety':>8} {'order qty':>10}")
    for r in res:
        print(f"{r['item']:<24} {r['reorder_point']:>10} {r['safety_stock']:>8} {r['order_quantity']:>10}")
    print(f"-> {a.out}")

if __name__ == "__main__":
    main()
