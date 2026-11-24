#!/usr/bin/env python3
"""Normalise a points list (CSV, XLSX or PDF table) into points.json.

Usage:
    python parse_points.py POINTS_FILE [--sheet NAME] [--out points.json] [--map field=Header ...]

Every point gets: id, system, equipment, description, name, rw, units, asset.
`id` is taken from a '#'/'No'/'ID' column when present, otherwise the row number.
"""
import argparse, csv, json, re, sys
from collections import Counter
from pathlib import Path

FIELDS = {
    "id": ["#", "no", "no.", "id", "point id", "point no", "row", "s/n", "sn", "item"],
    "system": ["system", "discipline", "subsystem", "sub system", "service"],
    "equipment": ["equipment", "equipment type", "asset type", "device type", "equipment class", "class", "object type"],
    "description": ["point", "description", "point description", "point name", "signal", "parameter", "point label"],
    "name": ["dbo point name", "dbo name", "dbo", "brick", "brick class", "haystack", "tag", "tag name", "object name",
             "standard name", "bacnet name", "point tag", "name"],
    "rw": ["read/write", "r/w", "rw", "access", "read write", "direction"],
    "units": ["units", "unit", "eng units", "engineering units", "format", "data type", "type"],
    "asset": ["asset", "equipment id", "equipment name", "device", "device name", "instance", "location"],
}

def norm(h):
    return re.sub(r"\s+", " ", str(h or "").strip().lower())

def detect_columns(header, overrides):
    cols = {}
    hn = [norm(h) for h in header]
    for field, header_name in overrides.items():
        if norm(header_name) in hn:
            cols[field] = hn.index(norm(header_name))
    for field, synonyms in FIELDS.items():
        if field in cols:
            continue
        for syn in synonyms:
            if syn in hn and hn.index(syn) not in cols.values():
                cols[field] = hn.index(syn)
                break
    return cols

def find_header(rows, overrides):
    best, best_i = {}, None
    for i, row in enumerate(rows[:40]):
        cols = detect_columns(row, overrides)
        if len(cols) > len(best):
            best, best_i = cols, i
    if best_i is None or len(best) < 2 or not ({"description", "name"} & set(best)):
        sys.exit("Could not find a header row with a point name or description column. Use --map name=<Header>.")
    return best_i, best

def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [row for row in csv.reader(f)]

def read_xlsx(path, sheet):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    return [["" if v is None else v for v in row] for row in ws.iter_rows(values_only=True)]

def read_pdf(path):
    try:
        import pdfplumber
    except ImportError:
        sys.exit("PDF input needs pdfplumber (pip install pdfplumber), or export the table to CSV/XLSX.")
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend([[c or "" for c in r] for r in table])
    if not rows:
        sys.exit("No tables found in the PDF. Export the points list to CSV or XLSX.")
    return rows

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("points_file")
    ap.add_argument("--sheet")
    ap.add_argument("--out", default="points.json")
    ap.add_argument("--map", nargs="*", default=[], help="field=Header overrides, e.g. name='DBO Point Name'")
    a = ap.parse_args()
    overrides = {}
    for m in a.map:
        if "=" in m:
            k, v = m.split("=", 1)
            overrides[k.strip()] = v.strip()
    p = Path(a.points_file)
    ext = p.suffix.lower()
    rows = read_csv(p) if ext in (".csv", ".txt") else read_xlsx(p, a.sheet) if ext in (".xlsx", ".xlsm") else read_pdf(p) if ext == ".pdf" else sys.exit(f"Unsupported file type: {ext}")

    hi, cols = find_header(rows, overrides)
    header = rows[hi]
    points, seen = [], set()
    for n, row in enumerate(rows[hi + 1:], 1):
        get = lambda f: str(row[cols[f]]).strip() if f in cols and cols[f] < len(row) and row[cols[f]] not in (None, "") else ""
        if [str(c).strip() for c in row[:len(header)]] == [str(h).strip() for h in header]:
            continue  # repeated header (multi-page PDFs)
        desc, name = get("description"), get("name")
        if not desc and not name:
            continue
        raw_id = get("id")
        pid = int(float(raw_id)) if re.fullmatch(r"\d+(\.0)?", raw_id or "") else (raw_id or n)
        if pid in seen:
            continue
        seen.add(pid)
        points.append({
            "id": pid, "system": get("system"), "equipment": get("equipment"), "description": desc,
            "name": "" if name.upper() in ("N/A", "NA", "-") else name,
            "rw": get("rw").upper(), "units": get("units"), "asset": get("asset"),
        })
    out = {"source": str(p.name), "columns": {f: str(header[i]) for f, i in cols.items()}, "count": len(points), "points": points}
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1))

    print(f"Read {len(points)} points from {p.name} -> {a.out}")
    print("Columns:", ", ".join(f"{f}='{h}'" for f, h in out["columns"].items()))
    by_sys = Counter(pt["system"] or "(no system)" for pt in points)
    for s, c in by_sys.most_common():
        print(f"  {s:<30} {c:>5}")
    writable = sum(1 for pt in points if "W" in pt["rw"])
    print(f"Writable (R/W) points: {writable}")

if __name__ == "__main__":
    main()
