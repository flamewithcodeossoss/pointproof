# assessment.json

The agent writes this file; `validate.py` checks it and `build_report.py` turns it into the Excel report.

```json
{
  "project": "Harbor Tower (demo)",
  "points_file": "points.json",
  "policy": {"max_method": "statistics"},
  "items": [
    {
      "ref": "R1",
      "title": "Weather-normalised energy baseline",
      "verdict": "applicable",
      "usecase": "energy-baseline",
      "method": ["statistics", "genai"],
      "why": "One regression equation per meter; no ML training.",
      "points": [
        {"id": 41, "name": "active_energy_import_sensor"},
        {"id": 7,  "name": "outdoor_air_temperature_sensor"}
      ],
      "other_inputs": "Weather API; building calendar.",
      "logic": ["Daily total per meter.", "Fit kWh = a + b × CDD.", "Expected vs actual every day."],
      "output": "AI tags per meter: expected kWh, deviation %.",
      "example": "Main meter, 21 Nov: actual 18,420 kWh; expected 16,950 kWh; +8.7%.",
      "runs": "Daily; refit monthly",
      "history": "3 months",
      "missing": ["Floor area per building (master data)"]
    },
    {"ref": "R7", "title": "24–72 h demand forecast", "verdict": "out_of_scope"}
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
| `usecase` | no | Library id from `usecases.yaml`, if one fits |
| `method` | applicable | List from `rules`, `statistics`, `ml`, `genai` |
| `why` | applicable | One or two sentences: why the method is enough |
| `points` | applicable | Every point by `id` **and** `name` exactly as in `points.json`. Never a point that is not there |
| `no_points_reason` | if `points` is empty | e.g. "Uses only the CMMS API" |
| `other_inputs` | no | Master data, external services |
| `logic` | applicable | Ordered steps; thresholds marked as examples |
| `output` | applicable | What goes back to the platform, and its shape |
| `example` | applicable | One example with illustrative values |
| `runs`, `history` | no | Frequency; data needed before it works |
| `missing` | no | Points or data that are needed but not in the list |
| `architecture` | no | Optional layer table for the report |

Out-of-scope items need only `ref`, `title` and `verdict`.
