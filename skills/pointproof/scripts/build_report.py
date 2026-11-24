#!/usr/bin/env python3
"""Build the one-sheet Excel report from a validated assessment.

Usage:
    python build_report.py assessment.json points.json [--out PointProof_report.xlsx]

Run validate.py first; this script refuses an assessment that fails validation.
"""
import argparse, json, math, sys
from collections import OrderedDict
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import validate  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

FONT = "Arial"
WIDTH = {"A": 11, "B": 28, "C": 36, "D": 50, "E": 32, "F": 56, "G": 38, "H": 46, "I": 17, "J": 19}
THIN = Side(style="thin", color="B7BEC6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR = PatternFill("solid", fgColor="2F4558")
SEC = PatternFill("solid", fgColor="E4E9EE")
ZEB = PatternFill("solid", fgColor="F6F8FA")
WRAP = Alignment(wrap_text=True, vertical="top")

class Sheet:
    def __init__(self, ws):
        self.ws = ws
        for c, w in WIDTH.items():
            ws.column_dimensions[c].width = w

    def put(self, r, c, v, bold=False, size=10, fill=None, color="000000", border=True, align=WRAP, italic=False, fmt=None):
        cell = self.ws.cell(row=r, column=c, value=v)
        cell.font = Font(name=FONT, size=size, bold=bold, color=color, italic=italic)
        cell.alignment = align
        if fill: cell.fill = fill
        if border: cell.border = BORDER
        if fmt: cell.number_format = fmt
        return cell

    def merge(self, r, c1, c2, v, **k):
        self.put(r, c1, v, **k)
        for c in range(c1 + 1, c2 + 1):
            if k.get("border", True): self.ws.cell(row=r, column=c).border = BORDER
            if k.get("fill"): self.ws.cell(row=r, column=c).fill = k["fill"]
        if c2 > c1:
            self.ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)

    def section(self, r, title):
        self.merge(r, 1, 10, title, bold=True, size=12, fill=SEC)
        self.ws.row_dimensions[r].height = 20

    def height(self, r, lines):
        self.ws.row_dimensions[r].height = min(409, 12.8 * lines + 8)

def est_lines(text, width, factor=1.25):
    if not text: return 1
    chars = max(width * factor, 8)
    return sum(max(1, math.ceil(len(seg) / chars)) for seg in str(text).split("\n"))

def width_of(c1, c2):
    return sum(WIDTH[get_column_letter(c)] for c in range(c1, c2 + 1))

def points_text(refs, by_id):
    groups = OrderedDict()
    for ref in refs:
        p = by_id[str(ref["id"])]
        label = p.get("name") or p.get("description")
        rw = " (R/W)" if "W" in (p.get("rw") or "") and "R" in (p.get("rw") or "") else (" (W)" if p.get("rw") == "W" else "")
        group = p.get("equipment") or p.get("system") or "Points"
        groups.setdefault(group, []).append(f"#{p['id']} {label}{rw}")
    return "\n".join(f"{g}: " + "; ".join(v) for g, v in groups.items())

def build(assessment, points, out):
    by_id = {str(p["id"]): p for p in points}
    items = assessment.get("items", [])
    app = [i for i in items if i.get("verdict") == "applicable"]
    oos = [i for i in items if i.get("verdict") == "out_of_scope"]

    wb = Workbook(); ws = wb.active; ws.title = "PointProof"
    S = Sheet(ws); r = 1
    S.merge(r, 1, 10, f"{assessment.get('project', 'Project')} — AI use cases proven against the points list", bold=True, size=14, border=False, align=Alignment(vertical="center"))
    ws.row_dimensions[r].height = 24; r += 1
    S.merge(r, 1, 10, f"Points source: {assessment.get('points_source', 'points list')}. \"#\" is the point id in that list. Every point below was checked to exist (PointProof validate). Thresholds are examples to confirm with the owner; example outputs use illustrative values.",
            size=9, color="4A5560", border=False, italic=True)
    ws.row_dimensions[r].height = 26; r += 1
    sum_row = r; r += 2

    S.section(r, "A. Applicable"); r += 1
    heads = ["Ref", "Requirement", "Method and why", "Input points (# and name)", "Other inputs", "Logic", "Output", "Example output (illustrative values)", "Runs", "History needed"]
    for i, h in enumerate(heads, 1): S.put(r, i, h, bold=True, color="FFFFFF", fill=HDR)
    ws.row_dimensions[r].height = 30; a_first = r + 1; r += 1
    for k, it in enumerate(app):
        methods = it.get("method") or []
        methods = [methods] if isinstance(methods, str) else methods
        why = f"{' + '.join(methods).upper()}. {it.get('why', '')}".strip()
        pts = points_text(it.get("points") or [], by_id) or it.get("no_points_reason", "")
        vals = [it.get("ref"), it.get("title"), why, pts, it.get("other_inputs", ""),
                "\n".join(f"• {s}" for s in it.get("logic", [])), it.get("output", ""), it.get("example", ""), it.get("runs", ""), it.get("history", "")]
        fill = ZEB if k % 2 else None
        for i, v in enumerate(vals, 1): S.put(r, i, v, bold=(i == 1), fill=fill)
        S.height(r, max(est_lines(v, WIDTH[get_column_letter(i)], 1.0 if i == 4 else 1.25) for i, v in enumerate(vals, 1)))
        r += 1
    a_last = r - 1; r += 1

    S.section(r, "B. Out of scope"); r += 1
    S.put(r, 1, "Ref", bold=True, color="FFFFFF", fill=HDR); S.merge(r, 2, 4, "Requirement", bold=True, color="FFFFFF", fill=HDR)
    S.merge(r, 5, 10, "Reason", bold=True, color="FFFFFF", fill=HDR); r += 1
    b_first = r
    for k, it in enumerate(oos):
        fill = ZEB if k % 2 else None
        S.put(r, 1, it.get("ref"), bold=True, fill=fill); S.merge(r, 2, 4, it.get("title"), fill=fill)
        S.merge(r, 5, 10, it.get("reason", ""), fill=fill)
        S.height(r, max(est_lines(it.get("title"), width_of(2, 4)), est_lines(it.get("reason"), width_of(5, 10)))); r += 1
    b_last = r - 1; r += 1

    gaps = [(it["ref"], g) for it in app for g in it.get("missing", [])]
    if gaps:
        S.section(r, "C. Missing points and data to request"); r += 1
        S.put(r, 1, "Ref", bold=True, color="FFFFFF", fill=HDR); S.merge(r, 2, 6, "Needed but not in the points list", bold=True, color="FFFFFF", fill=HDR); r += 1
        for k, (ref, g) in enumerate(gaps):
            fill = ZEB if k % 2 else None
            S.put(r, 1, ref, bold=True, fill=fill); S.merge(r, 2, 6, g, fill=fill); r += 1
        r += 1

    S.section(r, "D. Points used per system"); r += 1
    for c, h in zip(range(2, 6), ["System", "Points in list", "Used by applicable items", "Share used"]):
        S.put(r, c, h, bold=True, color="FFFFFF", fill=HDR)
    r += 1
    used = {}
    for it in app:
        for ref in it.get("points") or []:
            p = by_id[str(ref["id"])]
            used.setdefault(p.get("system") or "(no system)", set()).add(str(p["id"]))
    systems = OrderedDict()
    for p in points:
        systems.setdefault(p.get("system") or "(no system)", 0)
        systems[p.get("system") or "(no system)"] += 1
    u_first = r
    right = Alignment(horizontal="right", vertical="top")
    for s, n in systems.items():
        S.put(r, 2, s); S.put(r, 3, n, align=right); S.put(r, 4, len(used.get(s, ())), align=right)
        S.put(r, 5, f"=IF(C{r}=0,0,D{r}/C{r})", fmt="0%", align=right); r += 1
    u_last = r - 1
    S.put(r, 2, "Total", bold=True); S.put(r, 3, f"=SUM(C{u_first}:C{u_last})", bold=True, align=right)
    S.put(r, 4, f"=SUM(D{u_first}:D{u_last})", bold=True, align=right); S.put(r, 5, f"=IF(C{r}=0,0,D{r}/C{r})", bold=True, fmt="0%", align=right)
    r += 2

    arch = assessment.get("architecture") or []
    if arch:
        S.section(r, "E. Architecture"); r += 1
        S.put(r, 1, "#", bold=True, color="FFFFFF", fill=HDR); S.put(r, 2, "Layer", bold=True, color="FFFFFF", fill=HDR)
        S.merge(r, 3, 5, "What it does", bold=True, color="FFFFFF", fill=HDR); S.merge(r, 6, 8, "Data and points used", bold=True, color="FFFFFF", fill=HDR)
        S.merge(r, 9, 10, "Owner", bold=True, color="FFFFFF", fill=HDR); r += 1
        for k, L in enumerate(arch, 1):
            fill = ZEB if k % 2 == 0 else None
            S.put(r, 1, k, bold=True, fill=fill, align=Alignment(horizontal="left", vertical="top", wrap_text=True)); S.put(r, 2, L.get("layer"), bold=True, fill=fill)
            S.merge(r, 3, 5, L.get("does"), fill=fill); S.merge(r, 6, 8, L.get("data"), fill=fill); S.merge(r, 9, 10, L.get("owner"), fill=fill)
            S.height(r, max(est_lines(L.get("does"), width_of(3, 5)), est_lines(L.get("data"), width_of(6, 8)), est_lines(L.get("layer"), WIDTH["B"])))
            r += 1

    left = Alignment(horizontal="left", vertical="center")
    S.put(sum_row, 1, "Applicable", bold=True, border=False, align=left)
    S.put(sum_row, 2, f"=COUNTA(A{a_first}:A{a_last})" if app else 0, bold=True, border=False, align=left)
    S.put(sum_row, 3, "Out of scope", bold=True, border=False, align=Alignment(horizontal="right", vertical="center"))
    S.put(sum_row, 4, f"=COUNTA(A{b_first}:A{b_last})" if oos else 0, bold=True, border=False, align=left)
    S.put(sum_row, 5, "Total requirements", bold=True, border=False, align=Alignment(horizontal="right", vertical="center"))
    S.put(sum_row, 6, f"=B{sum_row}+D{sum_row}", bold=True, border=False, align=left)

    ws.sheet_view.zoomScale = 90
    ws.page_setup.orientation = "landscape"; ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return len(app), len(oos)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("assessment"); ap.add_argument("points_json")
    ap.add_argument("--out", default="PointProof_report.xlsx")
    a = ap.parse_args()
    assessment = json.loads(Path(a.assessment).read_text(encoding="utf-8"))
    pdata = json.loads(Path(a.points_json).read_text(encoding="utf-8"))
    assessment.setdefault("points_source", pdata.get("source", "points list"))
    errors, _ = validate(assessment, pdata["points"], (assessment.get("policy") or {}).get("max_method") or "ml")
    if errors:
        print("Assessment fails validation; run validate.py and fix:"); [print(" ", e) for e in errors]; sys.exit(1)
    n_app, n_oos = build(assessment, pdata["points"], a.out)
    print(f"Report: {a.out} ({n_app} applicable, {n_oos} out of scope)")

if __name__ == "__main__":
    main()
