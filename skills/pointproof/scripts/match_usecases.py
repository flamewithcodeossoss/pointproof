#!/usr/bin/env python3
"""Match the use-case library against a points list.

Usage:
    python match_usecases.py points.json [--library usecases.yaml] [--out candidates.json]

For every library use case it lists the points that fill each slot and a status:
  ready    all required slots have at least one point
  partial  some required slots are filled
  blocked  no required slot is filled
The agent uses candidates.json as a starting point; it still decides the verdict per requirement.
"""
import argparse, json, re
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_LIB = HERE.parent / "references" / "usecases.yaml"

def text_of(p):
    return f"{p.get('name','')} {p.get('description','')}".lower()

def slot_matches(slot, p):
    m = slot.get("match", {})
    t = text_of(p)
    if not any(re.search(pat.lower(), t) for pat in m.get("name", [])):
        return False
    if any(re.search(pat.lower(), t) for pat in m.get("exclude", [])):
        return False
    eq = m.get("equipment")
    if eq and not any(re.search(e.lower(), f"{p.get('system','')} {p.get('equipment','')}".lower()) for e in eq):
        return False
    if slot.get("writable") and "W" not in (p.get("rw") or ""):
        return False
    return True

def match(points, library):
    results = []
    for uc in library["usecases"]:
        slots = []
        for s in uc["slots"]:
            ids = [p["id"] for p in points if slot_matches(s, p)]
            slots.append({"key": s["key"], "label": s["label"], "required": bool(s.get("required")),
                          "writable": bool(s.get("writable")), "count": len(ids), "point_ids": ids[:60]})
        req = [s for s in slots if s["required"]]
        filled = [s for s in req if s["count"]]
        status = "ready" if req and len(filled) == len(req) else ("partial" if filled else "blocked")
        results.append({"usecase": uc["id"], "title": uc["title"], "method": uc["method"], "status": status,
                        "missing_required": [s["label"] for s in req if not s["count"]], "slots": slots})
    return results

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("points_json")
    ap.add_argument("--library", default=str(DEFAULT_LIB))
    ap.add_argument("--out", default="candidates.json")
    a = ap.parse_args()
    points = json.loads(Path(a.points_json).read_text())["points"]
    library = yaml.safe_load(Path(a.library).read_text())
    res = match(points, library)
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"{'use case':<30} {'method':<22} {'status':<8} missing")
    for r in res:
        print(f"{r['usecase']:<30} {'+'.join(r['method']):<22} {r['status']:<8} {'; '.join(r['missing_required'])}")
    print(f"-> {a.out}")

if __name__ == "__main__":
    main()
