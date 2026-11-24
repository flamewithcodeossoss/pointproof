#!/usr/bin/env python3
"""Normalise a points list (CSV, TSV, XLSX or PDF table) into points.json.

Usage:
    python parse_points.py POINTS_FILE [--sheet NAME] [--out points.json] [--map field=Header ...]

Every point gets: id, system, equipment, description, name, rw, units, asset.
`id` is taken from a '#'/'No'/'ID' column when present, otherwise the row number.
`rw` is normalised to R, W, R/W or "" (unknown) from values such as Read/Write, RW,
Input/Output or BACnet/IO types (AI, AO, BI, BO, DI, DO, AV, BV, MV).
CSV files may be comma, semicolon, tab or pipe separated, in UTF-8 or Windows-1252.
Without --sheet, the workbook sheet with the best header row is used.
"""
import argparse, csv, io, json, re, sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

FIELDS = {
    "id": ["#", "no", "no.", "id", "point id", "point no", "point number", "row", "s/n", "sn", "sr", "sr.", "item", "index"],
    "system": ["system", "discipline", "subsystem", "sub system", "sub-system", "service", "trade"],
    "equipment": ["equipment", "equipment type", "asset type", "device type", "equipment class", "class", "object type",
                  "equipment category"],
    "description": ["point", "description", "point description", "point name", "signal", "signal description",
                    "parameter", "point label", "label", "io description", "i/o description"],
    "name": ["dbo point name", "dbo name", "dbo", "brick", "brick class", "haystack", "tag", "tag name", "tagname",
             "object name", "standard name", "bacnet name", "point tag", "name", "tag id", "signal name", "variable",
             "variable name", "address", "point address"],
    "rw": ["read/write", "r/w", "rw", "access", "read write", "direction", "io type", "i/o type", "io", "i/o",
           "signal type", "point type"],
    "units": ["units", "unit", "eng units", "engineering units", "uom", "unit of measure", "units of measure"],
    "asset": ["asset", "equipment id", "equipment name", "device", "device name", "instance", "location", "panel",
              "controller"],
}
# Synonyms too generic to accept as a word inside a longer header ("Point Type", "Item Code").
NO_FUZZY = {"#", "no", "no.", "id", "row", "sn", "sr", "sr.", "item", "index", "name", "point", "class", "io", "i/o",
            "rw", "unit", "label", "device", "service", "access", "variable", "address", "instance"}
NA = {"N/A", "NA", "-", "--", "NONE", "NULL"}


def norm(h):
    return re.sub(r"\s+", " ", str(h if h is not None else "").strip().lower())


def detect_columns(header, overrides):
    cols = {}
    hn = [norm(h) for h in header]
    for field, header_name in overrides.items():
        if norm(header_name) in hn:
            cols[field] = hn.index(norm(header_name))
    # Pass 1: exact header names, in synonym priority order.
    for field, synonyms in FIELDS.items():
        if field in cols:
            continue
        for syn in synonyms:
            if syn in hn and hn.index(syn) not in cols.values():
                cols[field] = hn.index(syn)
                break
    # Pass 2: a synonym as whole words inside a longer header, e.g. "Tag Name (DBO)", "Units of measure".
    # The longest synonym wins, so "Equipment Description" is a description, not an equipment column.
    cands = []
    for field, synonyms in FIELDS.items():
        if field in cols:
            continue
        for syn in synonyms:
            if syn in NO_FUZZY:
                continue
            pat = re.compile(r"(?<![a-z0-9])" + re.escape(syn) + r"(?![a-z0-9])")
            cands += [(len(syn), field, i) for i, h in enumerate(hn) if pat.search(h)]
    for _, field, i in sorted(cands, key=lambda c: -c[0]):
        if field not in cols and i not in cols.values():
            cols[field] = i
    return cols


def find_header(rows, overrides):
    best, best_i = {}, None
    for i, row in enumerate(rows[:40]):
        cols = detect_columns(row, overrides)
        if len(cols) > len(best):
            best, best_i = cols, i
    if best_i is None or not ({"description", "name"} & set(best)):
        return None, {}
    return best_i, best


def decode(raw):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def read_csv(path):
    text = decode(Path(path).read_bytes())
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = "\t" if Path(path).suffix.lower() == ".tsv" else ","
    return [row for row in csv.reader(io.StringIO(text, newline=""), delimiter=delim)]


def read_xlsx(path, sheet, overrides):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    sheets = [wb[sheet]] if sheet else wb.worksheets
    best_rows, best_score = None, -1
    for ws in sheets:
        rows = [["" if v is None else v for v in row] for row in ws.iter_rows(values_only=True)]
        _, cols = find_header(rows, overrides)
        if len(cols) > best_score:
            best_rows, best_score = rows, len(cols)
            best_name = ws.title
    if not sheet and len(sheets) > 1:
        print(f"Using sheet '{best_name}' (use --sheet to choose another)")
    return best_rows or []


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


def norm_rw(v):
    """Map read/write and I/O direction values to R, W, R/W or '' (unknown)."""
    s = re.sub(r"[^A-Z]", " ", str(v).upper()).split()
    if not s:
        return ""
    words = set(s)
    joined = "".join(s)
    if joined in ("RW", "READWRITE", "WR") or {"READ", "WRITE"} <= words or {"R", "W"} <= words:
        return "R/W"
    if words & {"WRITE", "WRITABLE", "COMMANDABLE", "CONTROL", "COMMAND", "CMD", "SETPOINT", "OUTPUT", "OUT",
                "AO", "BO", "DO", "MO", "AV", "BV", "MV", "OUTPUTS"} or joined in ("W", "WO", "WRITEONLY"):
        # Outputs and BACnet value objects are commanded and can also be read back.
        return "W" if joined in ("W", "WO", "WRITEONLY") else "R/W"
    if words & {"READ", "READONLY", "INPUT", "IN", "AI", "BI", "DI", "MI", "MONITOR", "STATUS", "R", "RO", "INPUTS"}:
        return "R"
    return ""


def parse_id(raw):
    if re.fullmatch(r"\d+\.0+", raw):
        return int(float(raw))
    if re.fullmatch(r"[1-9]\d*|0", raw):
        return int(raw)
    return raw  # keep text ids and leading zeros ("001") exactly as written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("points_file")
    ap.add_argument("--sheet")
    ap.add_argument("--out", default="points.json")
    ap.add_argument("--map", nargs="*", default=[], help="field=Header overrides, e.g. name='DBO Point Name'")
    a = ap.parse_args()
    overrides = {}
    for m in a.map:
        if "=" not in m:
            sys.exit(f"--map expects field=Header, got {m!r}")
        k, v = (x.strip() for x in m.split("=", 1))
        if k not in FIELDS:
            sys.exit(f"--map: unknown field {k!r}; use one of {', '.join(FIELDS)}")
        overrides[k] = v
    p = Path(a.points_file)
    ext = p.suffix.lower()
    if ext in (".csv", ".txt", ".tsv"):
        rows = read_csv(p)
    elif ext in (".xlsx", ".xlsm"):
        rows = read_xlsx(p, a.sheet, overrides)
    elif ext == ".pdf":
        rows = read_pdf(p)
    else:
        sys.exit(f"Unsupported file type: {ext}. Save the list as CSV, TSV, XLSX or PDF.")

    hi, cols = find_header(rows, overrides)
    if hi is None:
        sys.exit("Could not find a header row with a point name or description column. Use --map name=<Header>.")
    header = rows[hi]
    header_names = [norm(h) for h in header]
    missing_maps = [f"{k}={v!r}" for k, v in overrides.items() if norm(v) not in header_names]
    if missing_maps:
        sys.exit(f"--map header not found in row {hi + 1}: {', '.join(missing_maps)}. Headers: {[str(h) for h in header]}")

    points, seen, by_raw_id, renamed = [], set(), {}, 0
    for n, row in enumerate(rows[hi + 1:], 1):
        get = lambda f: str(row[cols[f]]).strip() if f in cols and cols[f] < len(row) and row[cols[f]] not in (None, "") else ""
        if [str(c).strip() for c in row[:len(header)]] == [str(h).strip() for h in header]:
            continue  # repeated header (multi-page PDFs)
        desc, name = get("description"), get("name")
        if name.upper() in NA:
            name = ""
        if not desc and not name:
            continue
        raw_id = get("id")
        pid = parse_id(raw_id) if raw_id else n
        point = {
            "id": pid, "system": get("system"), "equipment": get("equipment"), "description": desc, "name": name,
            "rw": norm_rw(get("rw")), "units": get("units"), "asset": get("asset"),
        }
        key = str(pid)
        same_id = by_raw_id.setdefault(key, [])
        if any(all(q[f] == point[f] for f in ("name", "description", "asset", "system", "equipment")) for q in same_id):
            continue  # exact duplicate row
        same_id.append(point)
        if key in seen:
            k = 2
            while f"{pid}-{k}" in seen:
                k += 1
            point["id"] = key = f"{pid}-{k}"
            renamed += 1
        seen.add(key)
        points.append(point)
    out = {"source": str(p.name), "columns": {f: str(header[i]) for f, i in cols.items()}, "count": len(points), "points": points}
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Read {len(points)} points from {p.name} -> {a.out}")
    print("Columns:", ", ".join(f"{f}='{h}'" for f, h in out["columns"].items()))
    if renamed:
        print(f"WARN {renamed} point(s) repeat an id from column '{header[cols['id']]}'; they were given ids like "
              f"'<id>-2'. If ids restart per panel or sheet, rerun with --map id=<a unique column>.")
    by_sys = Counter(pt["system"] or "(no system)" for pt in points)
    for s, c in by_sys.most_common():
        print(f"  {s:<30} {c:>5}")
    if "rw" in cols:
        writable = sum(1 for pt in points if "W" in pt["rw"])
        unknown = sum(1 for pt in points if not pt["rw"])
        print(f"Writable points: {writable}" + (f" ({unknown} with an unrecognised read/write value)" if unknown else ""))
    else:
        print("No read/write column found: writable points cannot be confirmed (use --map rw=<Header> if there is one).")


if __name__ == "__main__":
    main()
