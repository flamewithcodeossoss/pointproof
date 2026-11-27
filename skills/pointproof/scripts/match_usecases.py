#!/usr/bin/env python3
"""Match the use-case library against a points list.

Usage:
    python match_usecases.py points.json [--domain buildings,water,...] [--library DIR_OR_FILE ...]
                             [--add-builtin] [--out candidates.json]

Domains: buildings, water, utilities, industrial, datacentres, general (default: all).
For every library use case it lists the points that fill each slot and a status:
  ready    all required slots have at least one point
  partial  some required slots are filled
  blocked  no required slot is filled
The agent uses candidates.json as a starting point; it still decides the verdict per requirement.

Names and descriptions are normalised first and compared as words: accents are dropped, camelCase is
split and abbreviations are expanded (SAT, CHWST, SP, kW...), so "AHU01.SATSP", "Supply Air Temp SP"
and "supplyAirTemperatureSetpoint" all read "supply air temperature setpoint". An underscore in a
library pattern matches any separator. A slot can also match on units (a kWh point fills an energy slot).
Pass --library more than once to add packs (a folder or a YAML file); a later pack replaces a use case
with the same id. --add-builtin loads the built-in library first.
"""
import argparse, json, re, sys
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from textnorm import point_texts, words  # noqa: E402

DEFAULT_LIB = HERE.parent / "references" / "usecases"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

_cache = {}


def rx(pattern):
    """Compile a library pattern; '_' in a pattern stands for any separator."""
    if pattern not in _cache:
        _cache[pattern] = re.compile(str(pattern).lower().replace("_", " "))
    return _cache[pattern]


def any_match(patterns, texts):
    return any(rx(p).search(t) for p in patterns for t in texts)


def load_library(path=DEFAULT_LIB, domains=None):
    """Load one folder of YAML files or one YAML file."""
    return load_libraries([path], domains)


def load_libraries(paths, domains=None):
    merged = {}
    for path in paths:
        path = Path(path)
        for f in (sorted(path.glob("*.yaml")) if path.is_dir() else [path]):
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            dom = d.get("domain", f.stem)
            for u in d.get("usecases", []):
                u.setdefault("domain", dom)
                if not domains or u["domain"] in domains:
                    merged[u["id"]] = u
    return {"usecases": list(merged.values())}


def slot_matches(slot, p):
    m = slot.get("match", {})
    texts = point_texts(p)
    units = str(p.get("units") or "").strip().lower()
    by_name = any_match(m.get("name", []), texts)
    by_units = bool(units) and any(re.fullmatch(str(u).lower(), units) for u in m.get("units", []))
    if not (by_name or by_units):
        return False
    if any_match(m.get("exclude", []), texts):
        return False
    eq = m.get("equipment")
    if eq:
        raw = f"{p.get('system', '')} {p.get('equipment', '')} {p.get('asset', '')}"
        if not any_match(eq, [words(raw), raw.lower()]):
            return False
    if slot.get("writable") and p.get("rw") and "W" not in p["rw"]:
        return False  # an empty R/W field means unknown: kept, and flagged below
    return True


def match(points, library):
    results = []
    for uc in library["usecases"]:
        slots = []
        for s in uc["slots"]:
            hits = [p for p in points if slot_matches(s, p)]
            ids = [p["id"] for p in hits]
            slot = {"key": s["key"], "label": s["label"], "required": bool(s.get("required")),
                    "writable": bool(s.get("writable")), "count": len(ids), "point_ids": ids[:60]}
            if s.get("writable"):
                unknown = [p["id"] for p in hits if not p.get("rw")]
                slot["writable_unknown_ids"] = unknown[:60]
                if unknown:
                    slot["writable_unverified"] = True
            slots.append(slot)
        req = [s for s in slots if s["required"]]
        filled = [s for s in req if s["count"]]
        status = "ready" if req and len(filled) == len(req) else ("partial" if filled else "blocked")
        results.append({"usecase": uc["id"], "domain": uc.get("domain", ""), "title": uc["title"], "method": uc["method"],
                        "solver": uc.get("solver"), "status": status,
                        "missing_required": [s["label"] for s in req if not s["count"]], "slots": slots})
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("points_json")
    ap.add_argument("--library", action="append", help="library folder or YAML file; repeat to add packs (default: built-in)")
    ap.add_argument("--add-builtin", action="store_true", help="load the built-in library before the --library packs")
    ap.add_argument("--domain", default="", help="comma-separated domains (default: all)")
    ap.add_argument("--out", default="candidates.json")
    a = ap.parse_args()
    libs = a.library or [str(DEFAULT_LIB)]
    if a.library and a.add_builtin:
        libs = [str(DEFAULT_LIB)] + libs
    points = json.loads(Path(a.points_json).read_text(encoding="utf-8"))["points"]
    domains = {d.strip() for d in a.domain.split(",") if d.strip()} or None
    res = match(points, load_libraries(libs, domains))
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'use case':<30} {'domain':<12} {'method':<24} {'status':<8} missing")
    for r in res:
        print(f"{r['usecase']:<30} {r['domain']:<12} {'+'.join(r['method']):<24} {r['status']:<8} {'; '.join(r['missing_required'])}")
    if any(s.get("writable_unverified") for r in res for s in r["slots"]):
        print("NOTE: some writable slots matched points with no read/write data (writable_unverified); confirm write access.")
    counts = {s: sum(1 for r in res if r["status"] == s) for s in ("ready", "partial", "blocked")}
    print(f"{len(res)} use cases: {counts['ready']} ready, {counts['partial']} partial, {counts['blocked']} blocked -> {a.out}")


if __name__ == "__main__":
    main()
