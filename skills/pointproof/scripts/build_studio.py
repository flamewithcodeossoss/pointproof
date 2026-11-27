#!/usr/bin/env python3
"""Build PointProof Studio: one self-contained HTML page to review and edit an assessment.

Usage:
    python build_studio.py [--assessment assessment.json] [--points points.json]
                           [--domain buildings,water,...] [--library DIR_OR_FILE] [--out studio.html]

Both inputs are optional. With only a points list the studio opens on the Suggest tab, so the user
can add library use cases as requirements; with neither, the user drops files onto the page.

In the studio the user can:
  - switch requirements in or out of scope and see coverage, the method ladder and points used update live
  - set the delivery policy (highest method) and a team capacity limit
  - edit methods, points, logic and outputs per requirement, with the same proof checks as validate.py
  - add requirements from the use-case library matched against the points
  - import a new points list (CSV or points.json) or assessment.json by drag and drop
  - export assessment.json (feed it back to validate.py / build_report.py), Excel, CSV, a PDF report,
    or the studio itself with the changes embedded
Edits are kept in the browser's local storage until exported.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from match_usecases import DEFAULT_LIB, load_library  # noqa: E402
from textnorm import ABBREV, COMPOUND  # noqa: E402

TEMPLATE = HERE.parent / "assets" / "studio_template.html"
LIB_FIELDS = ("id", "domain", "title", "method", "solver", "why", "slots", "external", "logic", "output", "runs", "history")

def build(assessment=None, points=None, library=None, domains=None):
    lib = {"usecases": [{k: u[k] for k in LIB_FIELDS if k in u} for u in (library or {"usecases": []})["usecases"]]}
    data = {"assessment": assessment, "points": points, "library": lib, "abbrev": ABBREV, "compound": COMPOUND.pattern,
            "domains": sorted(domains) if domains else None}
    # escape every "<" so no value can close or open a tag inside the data block
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = TEMPLATE.read_text(encoding="utf-8")
    if "__PP_DATA__" not in html:
        raise SystemExit("studio template is missing the __PP_DATA__ placeholder")
    return html.replace("__PP_DATA__", blob, 1)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assessment")
    ap.add_argument("--points")
    ap.add_argument("--library", default=str(DEFAULT_LIB))
    ap.add_argument("--domain", default="", help="comma-separated domains selected first in Suggest "
                    "(default: the domains the assessment already uses, else all); all stay available")
    ap.add_argument("--out", default="studio.html")
    a = ap.parse_args()
    assessment = json.loads(Path(a.assessment).read_text(encoding="utf-8")) if a.assessment else None
    points = json.loads(Path(a.points).read_text(encoding="utf-8")) if a.points else None
    domains = {d.strip() for d in a.domain.split(",") if d.strip()} or None
    library = load_library(a.library)
    Path(a.out).write_text(build(assessment, points, library, domains), encoding="utf-8")
    n_items = len((assessment or {}).get("items", []))
    n_pts = len((points or {}).get("points", []))
    print(f"wrote {a.out}: {n_items} requirements, {n_pts} points, {len(library['usecases'])} library use cases")

if __name__ == "__main__":
    main()
