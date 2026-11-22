import copy, json, subprocess, sys
from pathlib import Path

import yaml
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "pointproof" / "scripts"
EXAMPLE = ROOT / "examples" / "harbor-tower"
sys.path.insert(0, str(SCRIPTS))

from match_usecases import match  # noqa: E402
from validate import validate  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


def parse(tmp_path):
    out = tmp_path / "points.json"
    r = run(SCRIPTS / "parse_points.py", EXAMPLE / "points.csv", "--out", out)
    assert r.returncode == 0, r.stderr
    return json.loads(out.read_text())


def test_parse_reads_every_point(tmp_path):
    data = parse(tmp_path)
    assert data["count"] == 59
    p22 = next(p for p in data["points"] if p["id"] == 22)
    assert p22["name"] == "chilled_water_supply_temperature_setpoint"
    assert p22["rw"] == "R/W"


def test_library_is_well_formed():
    lib = yaml.safe_load((SCRIPTS.parent / "references" / "usecases.yaml").read_text())
    ids = [u["id"] for u in lib["usecases"]]
    assert len(ids) == len(set(ids))
    for u in lib["usecases"]:
        assert set(u["method"]) <= {"rules", "statistics", "ml", "genai"}
        assert any(s.get("required") for s in u["slots"]), u["id"]


def test_setpoint_slot_needs_a_writable_point(tmp_path):
    points = parse(tmp_path)["points"]
    lib = yaml.safe_load((SCRIPTS.parent / "references" / "usecases.yaml").read_text())
    res = {r["usecase"]: r for r in match(points, lib)}
    assert res["chw-setpoint-reset"]["status"] == "ready"
    for p in points:
        if p["id"] == 22:
            p["rw"] = "R"
    res = {r["usecase"]: r for r in match(points, lib)}
    assert res["chw-setpoint-reset"]["status"] == "partial"


def test_example_assessment_passes(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text())
    errors, _ = validate(a, points, "statistics")
    assert errors == []


def test_invented_point_fails(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text())
    bad = copy.deepcopy(a)
    bad["items"][0]["points"].append({"id": 999, "name": "ahu_power_sensor"})
    errors, _ = validate(bad, points, "ml")
    assert any("999" in e for e in errors)


def test_wrong_name_fails(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text())
    a["items"][0]["points"][0]["name"] = "made_up"
    errors, _ = validate(a, points, "ml")
    assert any("not 'made_up'" in e for e in errors)


def test_ml_above_policy_fails(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text())
    a["items"].append({"ref": "R99", "title": "Forecast", "verdict": "applicable", "method": ["ml"],
                       "points": [{"id": 32, "name": "active_energy_import_sensor"}]})
    assert any("above the policy" in e for e in validate(a, points, "statistics")[0])
    assert not any("above the policy" in e for e in validate(a, points, "ml")[0])


def test_report_builds(tmp_path):
    parse(tmp_path)
    out = tmp_path / "report.xlsx"
    r = run(SCRIPTS / "build_report.py", EXAMPLE / "assessment.json", tmp_path / "points.json", "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    ws = load_workbook(out).active
    refs = [c.value for c in ws["A"] if isinstance(c.value, str) and c.value.startswith("R")]
    assert "R1" in refs and "R12" in refs
