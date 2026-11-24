#!/usr/bin/env python3
"""Validate an assessment against the points list. No invented points get through.

Usage:
    python validate.py assessment.json points.json [--max-method rules|statistics|ml]

Errors (exit code 1):
  - a point id that is not in points.json
  - a point name that does not match the name in points.json for that id
  - an applicable item with no points and no `no_points_reason`
  - a verdict other than applicable / out_of_scope, or a duplicate ref
  - a method outside rules/statistics/ml/genai, or above --max-method
Warnings: applicable items without logic, output or example.
"""
import argparse, json, sys
from pathlib import Path

RANK = {"rules": 1, "statistics": 2, "ml": 3}
METHODS = set(RANK) | {"genai"}

def validate(assessment, points, max_method="ml"):
    by_id = {str(p["id"]): p for p in points}
    errors, warnings = [], []
    refs = set()
    limit = RANK.get(max_method, RANK["ml"])
    for it in assessment.get("items", []):
        ref = it.get("ref", "?")
        if ref in refs:
            errors.append(f"{ref}: duplicate ref")
        refs.add(ref)
        v = it.get("verdict")
        if v not in ("applicable", "out_of_scope"):
            errors.append(f"{ref}: verdict must be 'applicable' or 'out_of_scope' (got {v!r})")
            continue
        if v == "out_of_scope":
            continue
        methods = it.get("method") or []
        if isinstance(methods, str):
            methods = [methods]
        if not methods:
            errors.append(f"{ref}: applicable item needs a method")
        for m in methods:
            if m not in METHODS:
                errors.append(f"{ref}: unknown method {m!r}")
            elif m in RANK and RANK[m] > limit:
                errors.append(f"{ref}: method '{m}' is above the policy limit '{max_method}'; mark it out_of_scope or change the method")
        pts = it.get("points") or []
        if not pts and not it.get("no_points_reason"):
            errors.append(f"{ref}: applicable item has no points and no no_points_reason")
        for pt in pts:
            if not isinstance(pt, dict):
                errors.append(f"{ref}: point item must be an object with 'id' and 'name'")
                continue
            pid = str(pt.get("id"))
            if pid not in by_id:
                errors.append(f"{ref}: point id {pid} is not in the points list")
                continue
            real = by_id[pid].get("name") or by_id[pid].get("description")
            given = pt.get("name")
            if given and given != real:
                errors.append(f"{ref}: point {pid} is '{real}' in the points list, not '{given}'")
        for f in ("logic", "output", "example"):
            if not it.get(f):
                warnings.append(f"{ref}: no {f}")
    return errors, warnings

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("assessment")
    ap.add_argument("points_json")
    ap.add_argument("--max-method", choices=list(RANK), default=None)
    a = ap.parse_args()
    assessment = json.loads(Path(a.assessment).read_text())
    points = json.loads(Path(a.points_json).read_text())["points"]
    max_method = a.max_method or assessment.get("policy", {}).get("max_method", "ml")
    errors, warnings = validate(assessment, points, max_method)
    items = assessment.get("items", [])
    app = sum(1 for i in items if i.get("verdict") == "applicable")
    used = {str(p["id"]) for i in items for p in (i.get("points") or [])}
    print(f"{len(items)} items: {app} applicable, {len(items) - app} out of scope; {len(used)} distinct points referenced; policy max method: {max_method}")
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        sys.exit(1)
    print("PASSED: every referenced point exists in the points list")

if __name__ == "__main__":
    main()
