import copy, csv, json, re, subprocess, sys
from pathlib import Path

import pytest
import yaml
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "pointproof"
SCRIPTS = SKILL / "scripts"
OPT = SCRIPTS / "optimise"
EXAMPLE = ROOT / "examples" / "office-campus"
WATER = ROOT / "examples" / "water-network"
FORMATS = ROOT / "examples" / "formats"
OR_DATA = ROOT / "examples" / "or"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(OPT))

from adapters import detect, system_of  # noqa: E402
from parse_points import norm_rw  # noqa: E402
from match_usecases import load_libraries, load_library, match  # noqa: E402
from textnorm import normalise  # noqa: E402
from validate import RANK, validate  # noqa: E402

METHODS = set(RANK) | {"genai"}


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


def parse(tmp_path, src=EXAMPLE / "points.csv", *extra):
    out = tmp_path / f"{Path(src).stem}.json"
    r = run(SCRIPTS / "parse_points.py", src, "--out", out, *extra)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(out.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ parsing
def test_parse_reads_every_point(tmp_path):
    data = parse(tmp_path)
    assert data["count"] == 49
    by = {p["name"]: p for p in data["points"]}
    assert by["CH1.CHWSTSP"]["rw"] == "R/W" and by["CH1.CHWST"]["rw"] == "R"
    assert by["AHU1.SAT"]["equipment"] == "AHU-1" and by["AHU1.SAT"]["system"] == "HVAC"


@pytest.mark.parametrize("name,fmt,count", [
    ("brick_sample.ttl", "brick", 16),
    ("haystack_sample.json", "haystack", 6),
    ("ede_sample.csv", "ede", 8),
    ("opcua_nodeset.xml", "opcua", 6),
    ("historian_tags.csv", "table", 8),
])
def test_every_source_format_parses(tmp_path, name, fmt, count):
    if fmt == "brick":
        pytest.importorskip("rdflib")
    assert detect(FORMATS / name) == fmt
    data = parse(tmp_path, FORMATS / name)
    assert data["count"] == count
    for p in data["points"]:
        assert p["name"] or p["description"]
        assert p["rw"] in ("", "R", "W", "R/W")
    assert any(p["system"] for p in data["points"]), "system should be inferred"


def test_writable_points_are_detected_in_each_protocol(tmp_path):
    ede = parse(tmp_path, FORMATS / "ede_sample.csv")["points"]
    assert {p["rw"] for p in ede} == {"R", "R/W"}
    ua = parse(tmp_path, FORMATS / "opcua_nodeset.xml")["points"]
    assert any(p["rw"] == "R/W" for p in ua)
    hs = parse(tmp_path, FORMATS / "haystack_sample.json")["points"]
    assert any(p["rw"] == "R/W" and "sp" in p["name"] for p in hs)


def test_system_is_classified_by_equipment_first():
    assert system_of("Chiller 1", "chilled water supply temperature") == "HVAC"
    assert system_of("Main switchboard", "chiller power") == "Energy"
    assert system_of("DMA-01 inlet", "flow") == "Water"


@pytest.mark.parametrize("raw,expect", [
    ("AHU01.SATSP", "supply_air_temperature_setpoint"),
    ("Supply Air Temp SP", "supply_air_temperature_setpoint"),
    ("chwSupplyTemp", "chw_supply_temperature"),
    ("MTR3_kWh", "mtr_energy_kwh"),
])
def test_names_are_normalised(raw, expect):
    assert expect in normalise(raw)


# ------------------------------------------------------------------ library
def test_library_is_well_formed():
    lib = load_library()
    ids = [u["id"] for u in lib["usecases"]]
    assert len(ids) == len(set(ids))
    assert {u["domain"] for u in lib["usecases"]} == {"buildings", "water", "utilities", "industrial", "datacentres", "general"}
    for u in lib["usecases"]:
        assert set(u["method"]) <= METHODS, u["id"]
        assert any(s.get("required") for s in u["slots"]), u["id"]
        assert u.get("logic") and u.get("output"), u["id"]
        for s in u["slots"]:
            for pat in s["match"].get("name", []) + s["match"].get("exclude", []):
                re.compile(pat)
        if "optimisation" in u["method"]:
            assert u.get("solver"), f"{u['id']} should name its solver model"


def test_domain_filter():
    water = load_library(domains={"water"})
    assert water["usecases"] and all(u["domain"] == "water" for u in water["usecases"])


def test_setpoint_slot_needs_a_writable_point(tmp_path):
    points = parse(tmp_path)["points"]
    lib = load_library(domains={"buildings"})
    res = {r["usecase"]: r for r in match(points, lib)}
    assert res["chw-setpoint-reset"]["status"] == "ready"
    for p in points:
        if p["name"] == "CH1.CHWSTSP":
            p["rw"] = "R"
    res = {r["usecase"]: r for r in match(points, lib)}
    assert res["chw-setpoint-reset"]["status"] == "partial"


def test_unknown_write_access_is_flagged_not_dropped(tmp_path):
    points = parse(tmp_path)["points"]
    for p in points:
        p["rw"] = ""  # e.g. a historian export with no R/W column
    res = {r["usecase"]: r for r in match(points, load_library(domains={"buildings"}))}
    slot = next(s for s in res["chw-setpoint-reset"]["slots"] if s["writable"])
    assert res["chw-setpoint-reset"]["status"] == "ready"
    sp = next(p["id"] for p in points if p["name"] == "CH1.CHWSTSP")
    assert sp in slot["writable_unknown_ids"]


def test_vendor_tags_match_like_clean_names(tmp_path):
    points = parse(tmp_path, FORMATS / "historian_tags.csv")["points"]
    ready = {r["usecase"] for r in match(points, load_library(domains={"buildings"})) if r["status"] == "ready"}
    assert ready, "abbreviated historian tags should still fill library slots"


def test_water_example_is_all_ready():
    points = json.loads((WATER / "points.json").read_text())["points"]
    res = match(points, load_library(domains={"water"}))
    assert all(r["status"] == "ready" for r in res)


# ------------------------------------------------------------------ validation
@pytest.mark.parametrize("folder,policy", [(EXAMPLE, "optimisation"), (WATER, "optimisation")])
def test_example_assessments_pass(folder, policy):
    points = json.loads((folder / "points.json").read_text())["points"]
    a = json.loads((folder / "assessment.json").read_text())
    errors, _ = validate(a, points, policy)
    assert errors == []
    assert all(i.get("group") for i in a["items"] if i["verdict"] == "applicable")


def test_invented_point_fails(tmp_path):
    points = parse(tmp_path)["points"]
    bad = copy.deepcopy(json.loads((EXAMPLE / "assessment.json").read_text()))
    bad["items"][0]["points"].append({"id": 999, "name": "AHU9.KW"})
    errors, _ = validate(bad, points, "ml")
    assert any("999" in e for e in errors)


def test_wrong_name_fails(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text())
    a["items"][0]["points"][0]["name"] = "made_up"
    errors, _ = validate(a, points, "ml")
    assert any("not 'made_up'" in e for e in errors)


def test_method_ladder_policy(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text())
    pt = [{"id": 30, "name": "MTR.MAIN.KWH"}]
    a["items"] += [{"ref": "R98", "title": "Schedule", "verdict": "applicable", "method": ["optimisation"], "points": pt},
                   {"ref": "R99", "title": "Forecast", "verdict": "applicable", "method": ["ml", "genai"], "points": pt}]
    above = lambda pol: {e.split(":")[0] for e in validate(a, points, pol)[0] if "above the policy" in e} & {"R98", "R99"}
    assert above("statistics") == {"R98", "R99"}
    assert above("optimisation") == {"R99"}
    assert above("ml") == set()


def test_cli_reads_policy_from_the_file():
    r = run(SCRIPTS / "validate.py", WATER / "assessment.json", WATER / "points.json")
    assert r.returncode == 0 and "optimisation" in r.stdout, r.stdout + r.stderr


# ------------------------------------------------------------------ outputs
def test_report_builds(tmp_path):
    parse(tmp_path)
    out = tmp_path / "report.xlsx"
    r = run(SCRIPTS / "build_report.py", EXAMPLE / "assessment.json", tmp_path / "points.json", "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    ws = load_workbook(out).active
    refs = [c.value for c in ws["A"] if isinstance(c.value, str) and c.value.startswith("REQ-")]
    assert "REQ-01" in refs and "REQ-13" in refs


def test_studio_embeds_the_data(tmp_path):
    out = tmp_path / "studio.html"
    r = run(SCRIPTS / "build_studio.py", "--assessment", EXAMPLE / "assessment.json", "--points", EXAMPLE / "points.json",
            "--domain", "buildings", "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    html = out.read_text()
    assert "__PP_DATA__" not in html
    blob = re.search(r'<script type="application/json" id="pp-data">(.*?)</script>', html, re.S).group(1)
    data = json.loads(blob)
    assert len(data["assessment"]["items"]) == 13 and len(data["points"]["points"]) == 49
    assert data["domains"] == ["buildings"] and data["library"]["usecases"]
    assert data["abbrev"]["sat"] == "supply_air_temperature"


def test_studio_escapes_script_tags(tmp_path):
    a = json.loads((EXAMPLE / "assessment.json").read_text())
    a["items"][0]["why"] = "</script><script>alert(1)</script>"
    (tmp_path / "a.json").write_text(json.dumps(a))
    out = tmp_path / "studio.html"
    assert run(SCRIPTS / "build_studio.py", "--assessment", tmp_path / "a.json", "--out", out).returncode == 0
    assert "<script>alert(1)" not in out.read_text()


def test_studio_without_inputs_builds(tmp_path):
    out = tmp_path / "studio.html"
    assert run(SCRIPTS / "build_studio.py", "--out", out).returncode == 0
    assert "pp-data" in out.read_text()


# ------------------------------------------------------------------ optimisation rung
def rows(name):
    with open(OR_DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_reorder_policy():
    from reorder import plan
    res = plan(rows("consumables.csv"), 0.95)
    assert res and all(r["reorder_point"] >= r["safety_stock"] >= 0 and r["order_quantity"] > 0 for r in res)
    hi = {r["item"]: r["safety_stock"] for r in plan(rows("consumables.csv"), 0.99)}
    assert all(hi[r["item"]] >= r["safety_stock"] for r in res)


def test_budget_selection_respects_budget_and_groups():
    pytest.importorskip("ortools")
    from budget_select import select
    data = rows("retrofits.csv")
    res = select(data, 2_000_000)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")
    assert res["total_cost"] <= 2_000_000
    groups = [r["group"] for r in data if r["project"] in set(res["chosen"]) and r.get("group")]
    assert len(groups) == len(set(groups))


def test_maintenance_schedule_respects_capacity():
    pytest.importorskip("ortools")
    from schedule_maintenance import schedule
    plan = json.loads((OR_DATA / "maintenance_plan.json").read_text())
    res = schedule(plan)
    assert res["status"] in ("OPTIMAL", "FEASIBLE")
    assert all(0 <= u <= 1 for u in res["utilisation"].values())


def test_collection_routes_respect_vehicle_capacity():
    pytest.importorskip("ortools")
    from route_collection import plan
    res = plan(rows("bins.csv"), vehicles=2, capacity=6000)
    assert res["routes"]
    for r in res["routes"]:
        assert r["load_l"] <= 6000


# ------------------------------------------------------------------ robustness: any layout, encoding and naming
LIB = SKILL / "references" / "usecases"


def parse_file(tmp_path, name, content, *extra, encoding="utf-8"):
    src = tmp_path / name
    src.write_bytes(content if isinstance(content, bytes) else content.encode(encoding))
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
    cases = {"R/W": "R/W", "Read/Write": "R/W", "RW": "R/W", "Read only": "R", "R": "R", "RO": "R", "W": "W",
             "Analog Output": "R/W", "AO": "R/W", "BO": "R/W", "DI": "R", "Input": "R", "Output": "R/W", "": "", "?": ""}
    assert {k: norm_rw(k) for k in cases} == cases


def pts(*rows):
    return [dict(id=i, system="", equipment=eq, description=d, name=n, rw=rw, units=u, asset="")
            for i, (n, d, eq, rw, u) in enumerate(rows, 1)]


def test_matching_ignores_naming_style():
    lib = load_library(LIB)
    for run_name in ("AHU1 Run Status", "AHU1.RunStatus", "AHU1_RUN_STATUS", "ahu1-run-status"):
        points = pts((run_name, "", "AHU", "R", ""), ("AHU1 Schedule", "", "AHU", "R/W", ""))
        res = {r["usecase"]: r for r in match(points, lib)}
        assert res["ecm-out-of-hours"]["slots"][0]["point_ids"] == [1], run_name


def test_accents_are_ignored():
    lib = load_library(LIB)
    points = pts(("T1", "Température extérieure", "Météo", "R", "°C"), ("M1", "Énergie compteur", "Compteur", "R", "kWh"))
    slots = {s["key"]: s["point_ids"] for s in {r["usecase"]: r for r in match(points, lib)}["energy-baseline"]["slots"]}
    assert slots["energy"] == [2]


def test_short_tokens_do_not_match_inside_words():
    lib = load_library(LIB)
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
    points = pts(("EM-01.V3", "Incomer", "Meter", "R", "kWh"))
    res = {r["usecase"]: r for r in match(points, load_library(LIB))}
    assert res["energy-baseline"]["status"] == "ready"


def test_writable_slot_without_rw_data_is_flagged_not_blocked():
    points = pts(("Zone occupancy", "", "", "", ""), ("Zone temperature setpoint", "", "", "", ""))
    res = {r["usecase"]: r for r in match(points, load_library(LIB))}
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


def test_malformed_point_entry_fails(tmp_path):
    points = parse(tmp_path)["points"]
    bad = copy.deepcopy(json.loads((EXAMPLE / "assessment.json").read_text(encoding="utf-8")))
    bad["items"][0]["points"].append("invalid_format_string")
    assert any("must be an object" in e for e in validate(bad, points, "ml")[0])


def test_unknown_policy_is_an_error(tmp_path):
    points = parse(tmp_path)["points"]
    a = json.loads((EXAMPLE / "assessment.json").read_text(encoding="utf-8"))
    assert any("max_method" in e for e in validate(a, points, "statistic")[0])


def test_nested_output_dir_creation(tmp_path):
    parse(tmp_path)
    out = tmp_path / "sub" / "folder" / "nested_report.xlsx"
    r = run(SCRIPTS / "build_report.py", EXAMPLE / "assessment.json", tmp_path / "points.json", "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.exists()


def test_out_of_scope_reason_in_report(tmp_path):
    parse(tmp_path)
    out = tmp_path / "r.xlsx"
    r = run(SCRIPTS / "build_report.py", EXAMPLE / "assessment.json", tmp_path / "points.json", "--out", out)
    assert r.returncode == 0, r.stdout + r.stderr
    reasons = [i["reason"] for i in json.loads((EXAMPLE / "assessment.json").read_text(encoding="utf-8"))["items"] if i.get("reason")]
    cells = {c.value for row in load_workbook(out).active.iter_rows() for c in row}
    assert reasons and all(x in cells for x in reasons)
