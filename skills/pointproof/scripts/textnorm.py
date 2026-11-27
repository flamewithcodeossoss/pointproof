"""Normalise point names and descriptions so library patterns match any naming scheme.

'AHU01.SATSP', 'Supply Air Temp SP', 'supply_air_temperature_setpoint' and the Haystack tag set
'discharge air temp sp' all become comparable snake_case text with abbreviations expanded.
"""
import re, unicodedata

ABBREV = {
    "sat": "supply_air_temperature", "dat": "discharge_air_temperature", "rat": "return_air_temperature",
    "mat": "mixed_air_temperature", "oat": "outside_air_temperature", "oa": "outside_air", "ra": "return_air", "sa": "supply_air",
    "chwst": "chilled_water_supply_temperature", "chws": "chilled_water_supply_temperature",
    "chwrt": "chilled_water_return_temperature", "chwr": "chilled_water_return_temperature",
    "zt": "zone_air_temperature", "znt": "zone_air_temperature", "rmt": "room_temperature",
    "sp": "setpoint", "stpt": "setpoint", "spt": "setpoint", "temp": "temperature", "tmp": "temperature",
    "kw": "power_kw", "kwh": "energy_kwh", "rh": "humidity", "hum": "humidity", "dp": "differential_pressure",
    "chwv": "cooling_valve", "clgvlv": "cooling_valve", "vlv": "valve", "dmpr": "damper", "oad": "outdoor_air_damper",
    "spd": "speed", "cmd": "command", "sts": "status", "stat": "status", "run": "run_status", "flt": "fault_status",
    "alm": "alarm", "occ": "occupancy", "sched": "schedule", "hrs": "run_hours", "vfd": "vfd_speed",
    "pf": "power_factor", "flow": "flow_rate", "lvl": "level", "press": "pressure",
}
UNIT = re.compile(r"(?<![A-Za-z])[kMG](?:Wh|W|VAr|VAh|VA)(?![a-z])")
COMPOUND = re.compile(r"^(sat|dat|rat|mat|oat|chws|chwst|zt|znt|rmt)(sp|stpt|spt)$")

def fold(text):
    """Drop accents so 'Température' and 'Temperature' compare equal."""
    return "".join(c for c in unicodedata.normalize("NFKD", str(text or "")) if not unicodedata.combining(c))

def normalise(text):
    t = UNIT.sub(lambda m: m.group(0).lower(), fold(text))  # kWh, MW, kVAr stay one token
    t = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", t)
    tokens = [x for x in re.split(r"[^a-z0-9]+", t.lower()) if x]
    out = []
    for tok in tokens:
        tok = re.sub(r"^[a-z]+\d+$", lambda m: re.sub(r"\d+$", "", m.group(0)), tok) if re.fullmatch(r"(ahu|fcu|vav|ch|mtr|mdb|z|p|b)\d+", tok) else tok
        m = COMPOUND.match(tok)
        if m:
            out += [ABBREV[m.group(1)], "setpoint"]
        else:
            out.append(ABBREV.get(tok, tok))
    return re.sub(r"run_status_(hours|time)", r"run_\1", "_".join(out))  # "run hours" is not a run status

def words(text):
    """Normalised text as space-separated words, so regex word boundaries work: 'supply air temperature setpoint'."""
    return normalise(text).replace("_", " ")

def point_texts(p):
    """Name and description are matched separately, so anchored patterns ('power$') work on each."""
    return [t for t in (words(p.get("name")), words(p.get("description"))) if t]

def point_text(p):
    return " ".join(point_texts(p))
