#!/usr/bin/env python3
"""Match the use-case library against a points list.

Usage:
    python match_usecases.py points.json [--library usecases.yaml ...] [--out candidates.json]

For every library use case it lists the points that fill each slot and a status:
  ready    all required slots have at least one point
  partial  some required slots are filled
  blocked  no required slot is filled
The agent uses candidates.json as a starting point; it still decides the verdict per requirement.

Matching ignores naming style: "chilled_water_supply_temp", "Chilled Water Supply Temp",
"ChilledWaterSupplyTemp" and "CHW-SUPPLY.TEMP" are all compared as space-separated words,
and an underscore in a library pattern matches any separator.
Pass --library more than once to add domain packs; a later pack replaces a use case with the same id.
"""
import argparse, json, re, sys, unicodedata
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_LIB = HERE.parent / "references" / "usecases.yaml"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass


def words(s):
    """Lower-case, accent-folded text with every run of non-alphanumerics turned into one space."""
    s = "".join(c for c in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", " ", s.lower()).strip()


def variants(s):
    """The text as written and with camelCase split ("SupplyFanPower" -> "supply fan power")."""
    s = str(s or "")
    camel = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return {v for v in (words(s), words(camel)) if v}


_cache = {}


def rx(pattern):
    """Compile a library pattern; '_' in a pattern stands for any separator."""
    if pattern not in _cache:
        _cache[pattern] = re.compile(str(pattern).lower().replace("_", " "))
    return _cache[pattern]


def any_match(patterns, texts):
    return any(rx(p).search(t) for p in patterns for t in texts)


def slot_matches(slot, p, check_rw=True):
    m = slot.get("match", {})
    texts = variants(p.get("name")) | variants(p.get("description"))
    units = str(p.get("units") or "").strip().lower()
    by_name = any_match(m.get("name", []), texts)
    by_units = bool(units) and any(re.fullmatch(str(u).lower(), units) for u in m.get("units", []))
    if not (by_name or by_units):
        return False
    if any_match(m.get("exclude", []), texts):
        return False
    eq = m.get("equipment")
    if eq and not any_match(eq, variants(f"{p.get('system','')} {p.get('equipment','')} {p.get('asset','')}")):
        return False
    if check_rw and slot.get("writable") and "W" not in (p.get("rw") or ""):
        return False
    return True


def load_libraries(paths):
    merged = {}
    for path in paths:
        lib = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        for uc in lib.get("usecases", []):
            merged[uc["id"]] = uc
    return {"usecases": list(merged.values())}


def match(points, library):
    # A list with no read/write information cannot prove a point is writable; match on name
    # and flag the slot instead of reporting every setpoint use case as unfilled.
    check_rw = any(p.get("rw") for p in points)
    results = []
    for uc in library["usecases"]:
        slots = []
        for s in uc["slots"]:
            ids = [p["id"] for p in points if slot_matches(s, p, check_rw)]
            slot = {"key": s["key"], "label": s["label"], "required": bool(s.get("required")),
                    "writable": bool(s.get("writable")), "count": len(ids), "point_ids": ids[:60]}
            if s.get("writable") and not check_rw:
                slot["writable_unverified"] = True
            slots.append(slot)
        req = [s for s in slots if s["required"]]
        filled = [s for s in req if s["count"]]
        status = "ready" if req and len(filled) == len(req) else ("partial" if filled else "blocked")
        results.append({"usecase": uc["id"], "title": uc["title"], "method": uc["method"], "status": status,
                        "missing_required": [s["label"] for s in req if not s["count"]], "slots": slots})
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("points_json")
    ap.add_argument("--library", action="append", help="use-case library YAML; repeat to add packs (default: built-in)")
    ap.add_argument("--add-builtin", action="store_true", help="load the built-in library before the --library packs")
    ap.add_argument("--out", default="candidates.json")
    a = ap.parse_args()
    libs = a.library or [str(DEFAULT_LIB)]
    if a.library and a.add_builtin:
        libs = [str(DEFAULT_LIB)] + libs
    points = json.loads(Path(a.points_json).read_text(encoding="utf-8"))["points"]
    library = load_libraries(libs)
    res = match(points, library)
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'use case':<30} {'method':<22} {'status':<8} missing")
    for r in res:
        print(f"{r['usecase']:<30} {'+'.join(r['method']):<22} {r['status']:<8} {'; '.join(r['missing_required'])}")
    if not any(p.get("rw") for p in points):
        print("NOTE: the points list has no read/write data; writable slots matched on name only (writable_unverified).")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
