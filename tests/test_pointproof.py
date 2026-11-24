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


def test_malformed_point_entry_fails(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text())
    bad = copy.deepcopy(a)
    bad["items"][0]["points"].append("invalid_format_string")
    errors, _ = validate(bad, points, "ml")
    assert any("must be an object" in e for e in errors)


def test_nested_output_dir_creation(tmp_path):
    parse(tmp_path)
    out = tmp_path / "sub" / "folder" / "nested_report.xlsx"
    r = run(SCRIPTS / "build_report.py", EXAMPLE / "assessment.json", tmp_path / "points.json", "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.exists()


# --- Generality: any naming style, file layout, encoding and domain ---------------------------

from parse_points import norm_rw  # noqa: E402
from match_usecases import load_libraries  # noqa: E402

LIB = SCRIPTS.parent / "references" / "usecases.yaml"


def parse_file(tmp_path, name, content, *extra, encoding="utf-8"):
    src = tmp_path / name
    if isinstance(content, bytes):
        src.write_bytes(content)
    else:
        src.write_bytes(content.encode(encoding))
    out = tmp_path / (name + ".json")
    r = run(SCRIPTS / "parse_points.py", src, "--out", out, *extra)
    return r, (json.loads(out.read_text(encoding="utf-8")) if r.returncode == 0 else None)


def test_semicolon_csv_in_windows_1252(tmp_path):
    r, data = parse_file(tmp_path, "eu.csv", "Tag;Description;Units\nT1;Température départ;°C\n", encoding="cp1252")
    assert r.returncode == 0, r.stdout + r.stderr
    assert data["points"][0]["description"] == "Température départ"
    assert data["points"][0]["units"] == "°C"


def test_non_ascii_names_round_trip(tmp_path):
    r, data = parse_file(tmp_path, "intl.csv", "Tag,Description\nمضخة_1,ポンプ運転状態\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert data["points"][0]["name"] == "مضخة_1"


def test_tag_only_list(tmp_path):
    r, data = parse_file(tmp_path, "tags.csv", "Tag\nahu1_run_status\nahu1_fault_status\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert [p["name"] for p in data["points"]] == ["ahu1_run_status", "ahu1_fault_status"]


def test_header_words_inside_longer_headers(tmp_path):
    r, data = parse_file(tmp_path, "h.csv", "Point Number,Equipment Description,Tag Name (DBO),Units of Measure\n1,Pump 1 discharge pressure,P1_PT,bar\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert data["columns"] == {"id": "Point Number", "description": "Equipment Description",
                               "name": "Tag Name (DBO)", "units": "Units of Measure"}


def test_workbook_cover_sheet_is_skipped(tmp_path):
    from openpyxl import Workbook
    wb = Workbook(); wb.active.title = "Cover"; wb.active.append(["Points list, revision B"])
    ws = wb.create_sheet("IO List"); ws.append(["Tag", "Description"]); ws.append(["P1_RUN", "Pump 1 run status"])
    src = tmp_path / "list.xlsx"; wb.save(src)
    out = tmp_path / "p.json"
    r = run(SCRIPTS / "parse_points.py", src, "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["points"][0]["name"] == "P1_RUN"


def test_repeated_ids_are_kept_not_dropped(tmp_path):
    r, data = parse_file(tmp_path, "d.csv", "No,Panel,Tag\n1,P1,run_status\n1,P2,run_status\n1,P2,run_status\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert [p["id"] for p in data["points"]] == [1, "1-2"]  # exact duplicate row dropped, the other kept
    assert "WARN" in r.stdout


def test_map_rejects_unknown_field_and_missing_header(tmp_path):
    r, _ = parse_file(tmp_path, "m.csv", "Tag\nx\n", "--map", "nmae=Tag")
    assert r.returncode != 0 and "unknown field" in (r.stdout + r.stderr)
    r, _ = parse_file(tmp_path, "m2.csv", "Tag\nx\n", "--map", "name=Signal")
    assert r.returncode != 0 and "not found" in (r.stdout + r.stderr)


def test_read_write_values_are_normalised():
    cases = {"R/W": "R/W", "Read/Write": "R/W", "RW": "R/W", "Read only": "R", "R": "R", "W": "W",
             "Analog Output": "R/W", "AO": "R/W", "BO": "R/W", "DI": "R", "Input": "R", "Output": "R/W", "": "", "?": ""}
    assert {k: norm_rw(k) for k in cases} == cases


def pts(*rows):
    return [dict(id=i, system="", equipment=eq, description=d, name=n, rw=rw, units=u, asset="")
            for i, (n, d, eq, rw, u) in enumerate(rows, 1)]


def test_matching_ignores_naming_style():
    lib = load_libraries([LIB])
    for run_name in ("AHU1 Run Status", "AHU1.RunStatus", "AHU1_RUN_STATUS", "ahu1-run-status"):
        points = pts((run_name, "", "AHU", "R", ""), ("AHU1 Schedule", "", "AHU", "R/W", ""))
        res = {r["usecase"]: r for r in match(points, lib)}
        assert res["ecm-out-of-hours"]["slots"][0]["point_ids"] == [1], run_name


def test_short_tokens_do_not_match_inside_words():
    lib = load_libraries([LIB])
    points = pts(("Float switch", "Tank float level", "Tank", "R", ""),
                 ("MainMeter_kWh", "Main meter energy", "Meter", "R", "kWh"),
                 ("OAT", "Outside air temp", "Weather", "R", "°C"),
                 ("Fan1 Power", "", "Fan", "R", "kW"))
    res = {r["usecase"]: r for r in match(points, lib)}
    slots = {s["key"]: s["point_ids"] for s in res["energy-baseline"]["slots"]}
    assert slots["outdoor_temp"] == [3] and slots["energy"] == [2]
    power = {s["key"]: s["point_ids"] for s in res["fault-energy-cost"]["slots"]}["power"]
    assert power == [4]  # the kWh meter is energy, not power


def test_units_fill_a_slot_when_names_are_cryptic():
    lib = load_libraries([LIB])
    points = pts(("EM-01.V3", "Incomer", "Meter", "R", "kWh"))
    res = {r["usecase"]: r for r in match(points, lib)}
    assert res["energy-baseline"]["status"] == "ready"


def test_writable_slot_without_rw_data_is_flagged_not_blocked():
    lib = load_libraries([LIB])
    points = pts(("Zone occupancy", "", "", "", ""), ("Zone temperature setpoint", "", "", "", ""))
    res = {r["usecase"]: r for r in match(points, lib)}
    sp = res["zone-setback"]["slots"][1]
    assert res["zone-setback"]["status"] == "ready" and sp.get("writable_unverified")


def test_domain_pack_adds_and_overrides(tmp_path):
    pack = tmp_path / "pack.yaml"
    pack.write_text(yaml.safe_dump({"usecases": [
        {"id": "pump-cavitation", "title": "Pump cavitation", "method": ["rules"],
         "slots": [{"key": "p", "label": "Suction pressure", "required": True, "match": {"name": ["suction_pressure"]}}]},
        {"id": "short-cycling", "title": "Override", "method": ["rules"],
         "slots": [{"key": "r", "label": "Run", "required": True, "match": {"name": ["running"]}}]},
    ]}), encoding="utf-8")
    lib = load_libraries([LIB, pack])
    ids = [u["id"] for u in lib["usecases"]]
    assert "pump-cavitation" in ids and ids.count("short-cycling") == 1
    assert next(u for u in lib["usecases"] if u["id"] == "short-cycling")["title"] == "Override"


def test_unknown_policy_is_an_error(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text(encoding="utf-8"))
    errors, _ = validate(a, points, "statistic")
    assert any("max_method" in e for e in errors)


def test_out_of_scope_reason_in_report(tmp_path):
    parse(tmp_path)
    a = json.loads((EXAMPLE / "assessment.json").read_text(encoding="utf-8"))
    oos = next(i for i in a["items"] if i["verdict"] == "out_of_scope")
    oos["reason"] = "Needs ML; policy is statistics."
    src = tmp_path / "a.json"; src.write_text(json.dumps(a), encoding="utf-8")
    out = tmp_path / "r.xlsx"
    r = run(SCRIPTS / "build_report.py", src, tmp_path / "points.json", "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert any(c.value == "Needs ML; policy is statistics." for row in load_workbook(out).active.iter_rows() for c in row)
