"""Readers that turn building and industrial data sources into PointProof points.

Every reader returns a list of dicts with: system, equipment, description, name, rw, units, asset.
Supported: Brick (TTL/RDF), Project Haystack (JSON v3 grid or Hayson), BACnet EDE (CSV),
OPC UA NodeSet2 (XML). Tables (CSV/XLSX/PDF, Historian and PI tag exports) are read in parse_points.py.
"""
import csv, json, re
from pathlib import Path

# ----------------------------------------------------------------- detection
def detect(path):
    p = Path(path); ext = p.suffix.lower()
    if ext in (".ttl", ".n3", ".nt", ".rdf", ".owl", ".jsonld"):
        return "brick"
    if ext == ".xml":
        head = p.read_text(encoding="utf-8", errors="ignore")[:4000]
        return "opcua" if "UANodeSet" in head else "unknown"
    if ext == ".json":
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return "unknown"
        if isinstance(d, dict) and "points" in d:
            return "pointproof"
        if isinstance(d, dict) and "rows" in d:
            return "haystack"
        if isinstance(d, list) and d and isinstance(d[0], dict):
            return "haystack"
        return "unknown"
    if ext in (".csv", ".txt", ".tsv"):
        head = p.read_text(encoding="utf-8", errors="ignore")[:3000].lower()
        if "engineering-data-exchange" in head or ("keyname" in head and "object-name" in head):
            return "ede"
        return "table"
    if ext in (".xlsx", ".xlsm", ".pdf"):
        return "table"
    return "unknown"

def local(uri):
    return re.split(r"[#/:]", str(uri))[-1]

def snake(s):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(s))
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

SYSTEM_RULES = [
    (r"meter|mtr|elec|switchboard|mdb|panel|ups|pdu", "Energy"),
    (r"ahu|fcu|fan.?coil|vav|vrf|vrv|chiller|boiler|rtu|mau|crac|crah|cooling.?tower|hvac|zone|heat.?pump|cooling|heating", "HVAC"),
    (r"water|leak|tank|reservoir|pump.?station|valve.?chamber|dma|prv|well", "Water"),
    (r"light|luminaire|lux", "Lighting"),
    (r"lift|elevator|escalator", "Vertical transport"),
    (r"pump", "HVAC"),
]

def system_of(equip_text, point_text=""):
    """Classify by the equipment first, then by the point name."""
    for text in (equip_text or "", point_text or ""):
        t = text.lower()
        for pat, sys_ in SYSTEM_RULES:
            if re.search(pat, t):
                return sys_
    return ""

# ----------------------------------------------------------------- Brick
POINT_SUFFIX = re.compile(r"(Sensor|Setpoint|Command|Status|Alarm|Parameter|Point)$")

def read_brick(path):
    import rdflib
    from rdflib.namespace import RDF, RDFS
    g = rdflib.Graph(); g.parse(str(path))
    BRICK = rdflib.Namespace("https://brickschema.org/schema/Brick#")
    is_point_of = [BRICK.isPointOf, rdflib.URIRef("https://brickschema.org/schema/1.1/Brick#isPointOf")]
    has_point = [BRICK.hasPoint]
    owner = {}
    for pred in is_point_of:
        for s, o in g.subject_objects(pred):
            owner[s] = o
    for pred in has_point:
        for s, o in g.subject_objects(pred):
            owner.setdefault(o, s)
    subjects = set(owner)
    for s, t in g.subject_objects(RDF.type):
        if POINT_SUFFIX.search(local(t)):
            subjects.add(s)
    out = []
    for s in sorted(subjects, key=str):
        types = [local(t) for t in g.objects(s, RDF.type) if POINT_SUFFIX.search(local(t))]
        if not types:
            continue
        cls = types[0]
        eq = owner.get(s)
        eq_types = [local(t) for t in g.objects(eq, RDF.type)] if eq is not None else []
        label = next((str(l) for l in g.objects(s, RDFS.label)), local(s))
        unit = next((local(u) for u in g.objects(s, BRICK.hasUnit)), "")
        equip = eq_types[0].replace("_", " ") if eq_types else ""
        out.append({"system": system_of(" ".join(eq_types), cls) or "Brick", "equipment": equip,
                    "description": label, "name": snake(cls), "rw": "R/W" if re.search(r"Setpoint|Command$", cls) else "R",
                    "units": unit, "asset": local(eq) if eq is not None else ""})
    return out

# ----------------------------------------------------------------- Project Haystack
TAG_ORDER = ["discharge", "supply", "return", "outside", "mixed", "exhaust", "zone", "chilled", "hot", "condenser", "entering", "leaving",
             "air", "water", "elec", "co2", "humidity", "temp", "pressure", "flow", "power", "energy", "speed", "damper", "valve", "fan",
             "pump", "occupied", "occ", "run", "enable", "alarm", "fault", "effective", "sp", "cmd", "sensor"]
EQUIP_TAGS = ["ahu", "rtu", "mau", "fcu", "vav", "chiller", "boiler", "coolingTower", "pump", "meter", "elec", "water", "lighting",
              "lift", "elevator", "vrf", "crac", "fan", "tank", "plant"]

def hval(v):
    """Decode Haystack JSON v3 ('s:', 'm:', 'r:', 'n:') or Hayson ({'_kind': ...}) values."""
    if isinstance(v, dict):
        k = v.get("_kind")
        if k == "marker": return True
        if k == "ref": return {"ref": v.get("val"), "dis": v.get("dis")}
        if k == "number": return f"{v.get('val')} {v.get('unit', '')}".strip()
        return v.get("val")
    if isinstance(v, str):
        if v == "m:" or v == "✓": return True
        if v.startswith("s:"): return v[2:]
        if v.startswith("r:"):
            parts = v[2:].split(" ", 1)
            return {"ref": parts[0].lstrip("@"), "dis": parts[1] if len(parts) > 1 else None}
        if v.startswith("n:"): return v[2:]
    return v

def read_haystack(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = d["rows"] if isinstance(d, dict) else d
    rows = [{k: hval(v) for k, v in r.items()} for r in rows]
    by_id = {}
    for r in rows:
        rid = r.get("id")
        if isinstance(rid, dict): rid = rid.get("ref")
        if rid: by_id[str(rid).lstrip("@")] = r
    out = []
    for r in rows:
        if r.get("point") is not True:
            continue
        markers = [k for k, v in r.items() if v is True and k not in ("point", "his", "cur", "writable")]
        name = "_".join(sorted(markers, key=lambda t: TAG_ORDER.index(t) if t in TAG_ORDER else 99))
        eq_ref = r.get("equipRef"); eq = None; eq_dis = ""
        if isinstance(eq_ref, dict):
            eq = by_id.get(str(eq_ref.get("ref")).lstrip("@")); eq_dis = eq_ref.get("dis") or ""
        eq_markers = [k for k, v in (eq or {}).items() if v is True and k in EQUIP_TAGS] or [m for m in markers if m in EQUIP_TAGS]
        if eq and not eq_dis:
            eq_dis = eq.get("dis") or eq.get("navName") or ""
        rw = "R/W" if (r.get("writable") is True or "sp" in markers or "cmd" in markers) else "R"
        out.append({"system": system_of(" ".join(eq_markers), " ".join(markers)) or "Haystack", "equipment": " ".join(eq_markers).upper() or "",
                    "description": r.get("dis") or r.get("navName") or name, "name": name, "rw": rw,
                    "units": r.get("unit") or "", "asset": eq_dis})
    return out

# ----------------------------------------------------------------- BACnet EDE
OBJ = {0: "AI", 1: "AO", 2: "AV", 3: "BI", 4: "BO", 5: "BV", 13: "MI", 14: "MO", 19: "MV"}
UNITS = {19: "kWh", 29: "%RH", 47: "W", 48: "kW", 53: "Pa", 62: "°C", 64: "°F", 95: "", 96: "ppm", 98: "%"}

def read_ede(path):
    lines = Path(path).read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    hdr_i = next(i for i, l in enumerate(lines) if "keyname" in l.lower() and "object-name" in l.lower())
    header = [h.strip().lstrip("#").strip().lower() for h in lines[hdr_i].split(";")]
    col = {h: i for i, h in enumerate(header)}
    out = []
    for l in lines[hdr_i + 1:]:
        if not l.strip() or l.startswith("#"):
            continue
        f = [c.strip() for c in l.split(";")]
        get = lambda h: f[col[h]] if h in col and col[h] < len(f) else ""
        try:
            otype = int(get("object-type"))
        except ValueError:
            otype = -1
        obj = OBJ.get(otype, f"type {otype}")
        settable = get("settable").upper() in ("Y", "YES", "TRUE", "1")
        rw = "R/W" if obj in ("AO", "BO", "MO") or (obj in ("AV", "BV", "MV") and settable) else "R"
        name = get("object-name")
        asset = re.split(r"[._\-\s]", name, 1)[0] if re.search(r"[._\-\s]", name) else ""
        try:
            unit = UNITS.get(int(get("unit-code")), f"code {get('unit-code')}") if get("unit-code") else ""
        except ValueError:
            unit = get("unit-code")
        out.append({"system": system_of(asset, name) or "BACnet", "equipment": f"Device {get('device obj.-instance')} {obj}".strip(),
                    "description": get("description") or name, "name": name, "rw": rw, "units": unit, "asset": asset})
    return out

# ----------------------------------------------------------------- OPC UA NodeSet2
def read_opcua(path):
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    ns = {"ua": root.tag.split("}")[0].strip("{")}
    nodes = {}
    for el in root:
        nid = el.get("NodeId")
        if nid:
            dn = el.find("ua:DisplayName", ns)
            nodes[nid] = {"tag": el.tag.split("}")[-1], "browse": (el.get("BrowseName") or "").split(":")[-1],
                          "display": dn.text if dn is not None else "", "parent": el.get("ParentNodeId"), "el": el}
    meta = {"EngineeringUnits", "EURange", "InstrumentRange", "Definition", "ValuePrecision"}
    out = []
    for nid, n in nodes.items():
        if n["tag"] != "UAVariable" or n["browse"] in meta:
            continue
        parent = nodes.get(n["parent"] or "", {})
        el = n["el"]; desc = el.find("ua:Description", ns)
        access = int(el.get("AccessLevel", "1"))
        units = ""
        for cid, c in nodes.items():
            if c["parent"] == nid and c["browse"] == "EngineeringUnits":
                txt = "".join(c["el"].itertext())
                m = re.search(r"(°C|°F|kWh|kW|%RH|%|ppm|Pa|kPa|bar|m3/h|l/s|rpm|A|V)\b", txt)
                units = m.group(1) if m else ""
        eq = parent.get("display") or parent.get("browse") or ""
        out.append({"system": system_of(eq, n["browse"]) or "OPC UA", "equipment": eq,
                    "description": (desc.text if desc is not None else "") or n["display"] or n["browse"],
                    "name": snake(n["browse"]), "rw": "R/W" if access & 2 else "R", "units": units, "asset": eq})
    return out

READERS = {"brick": read_brick, "haystack": read_haystack, "ede": read_ede, "opcua": read_opcua}
