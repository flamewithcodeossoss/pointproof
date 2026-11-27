# assessment.json

The agent writes this file (or the user exports it from the studio); `validate.py` checks it, and `build_report.py` and `build_studio.py` turn it into the Excel report and the studio.

```json
{
  "project": "Northgate Office Campus (demo)",
  "points_source": "points.csv",
  "policy": {"max_method": "statistics"},
  "capacity": 8,
  "items": [
    {
      "ref": "REQ-02",
      "title": "Weather-corrected monthly energy performance",
      "verdict": "applicable",
      "group": "Energy",
      "usecase": "energy-baseline",
      "method": ["statistics", "genai"],
      "why": "One regression on cooling degree days and occupancy; no ML training.",
      "points": [
        {"id": 30, "name": "MTR.MAIN.KWH"},
        {"id": 29, "name": "WS.OAT"}
      ],
      "other_inputs": "Weather API; building calendar.",
      "logic": ["Daily total per meter.", "Fit kWh = a + b × CDD.", "Expected vs actual every day."],
      "output": "AI tags per meter: expected kWh, deviation %.",
      "example": "October: actual 212,400 kWh; expected 198,900 kWh; +6.8%.",
      "runs": "Daily; refit monthly",
      "history": "3 months",
      "missing": ["Floor area (master data)"]
    },
    {"ref": "REQ-12", "title": "Next-day building load forecast", "verdict": "out_of_scope", "reason": "Needs a trained ML model; the policy stops at optimisation."}
  ],
  "architecture": [
    {"layer": "Field systems", "does": "…", "data": "…", "owner": "…"}
  ]
}
```

## Fields

| Field | Required | Notes |
|---|---|---|
| `ref` | yes | The requirement's own reference; unique |
| `title` | yes | Short requirement title |
| `verdict` | yes | `applicable` or `out_of_scope` |
| `group` | no | Grouping for coverage (Energy, Maintenance, Network losses…) |
| `usecase` | no | Library id from `usecases/*.yaml`, if one fits |
| `method` | applicable | List from `rules`, `statistics`, `optimisation`, `ml`, `genai`; the highest of the first four must not exceed the policy |
| `solver` | no | For optimisation items: the model, e.g. `assignment (CP-SAT)`, `routing (CVRP)` |
| `why` | applicable | One or two sentences: why the method is enough |
| `points` | applicable | Every point by `id` **and** `name` exactly as in `points.json`. Never a point that is not there |
| `no_points_reason` | if `points` is empty | e.g. "Uses only the CMMS API" |
| `other_inputs` | no | Master data, external services |
| `logic` | applicable | Ordered steps; thresholds marked as examples |
| `output` | applicable | What goes back to the platform, and its shape |
| `example` | applicable | One example with illustrative values |
| `runs`, `history` | no | Frequency; data needed before it works |
| `missing` | no | Points or data that are needed but not in the list |
| `reason` | no | Out-of-scope items: one line on why (method above policy, missing points, third-party platform) |
| `architecture` | no | Optional layer table for the report |

Top level: `project`, `policy.max_method` (`rules`, `statistics`, `optimisation` or `ml`; default `ml`), optional `capacity` (items the team can deliver; the studio flags any overflow).

Out-of-scope items need only `ref`, `title` and `verdict`; `reason` is shown in the report and the studio when given.
