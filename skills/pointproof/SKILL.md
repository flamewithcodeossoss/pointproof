---
name: pointproof
description: Prove which AI use cases a building, plant or industrial site can really deliver from its points list (BMS, SCADA, PLC I/O, energy, IoT, CMMS). For each requirement it picks the simplest method (rules, statistics, ML or GenAI), lists the exact points it needs, flags missing data, and builds a validated Excel report. Use when given a points list, I/O list or tag list plus AI requirements, use cases, a tender or an RFP to scope.
---

# PointProof

Turn "we need AI for X" into a decision you can defend point by point: applicable or out of scope, the simplest method, the exact points from the client's own list, the logic, and the output. Every point in the report is checked against the points list, so nothing is invented.

## Inputs

1. **Points list**: CSV/TSV (any delimiter, UTF-8 or Windows-1252), XLSX or a PDF table, with a point name, tag or description column. Any naming style works (DBO, Brick, Haystack, vendor tags, plain-language descriptions, any language), from any domain (buildings, plants, utilities, process).
2. **Requirements**: the AI use cases to assess (a list, a table, or tender text). Give each a short `ref`.
3. **Policy** (ask if not given): the highest method the team will deliver — `rules`, `statistics` or `ml`. A team that does not deliver ML uses `statistics`.

If the points list or the requirements are missing, ask for them before starting.

## Workflow

Scripts are in `scripts/` next to this file; run them with Python 3.9+ (`pip install openpyxl pyyaml`, plus `pdfplumber` for PDF input).

1. **Parse the points list**
   `python scripts/parse_points.py <points file> --out points.json`
   Check the detected columns and any WARN lines in the output. If a column was missed or the wrong one was taken, rerun with `--map name="<Header>"` (fields: id, system, equipment, description, name, rw, units, asset). For a workbook it picks the sheet with the best header; use `--sheet` to choose another. If ids repeat (e.g. numbering restarts per panel), points get ids like `12-2`; map a unique column to `id` if there is one.

2. **Match the library**
   `python scripts/match_usecases.py points.json --out candidates.json`
   This shows which generic use cases in `references/usecases.yaml` the list can support (ready / partial / blocked) and which points fill each slot. Matching ignores naming style and also uses units (a `kWh` point fills an energy slot even with a cryptic tag). The library leans to buildings and energy; for other domains add a pack with `--library pack.yaml --add-builtin`, or reason from first principles in step 3. A slot marked `writable_unverified` means the list has no read/write data: list it in `missing` as "confirm the point is writable".

3. **Assess each requirement** and write `assessment.json` following `references/assessment_schema.md`:
   - Map the requirement to a library use case when one fits; otherwise reason from first principles.
   - Choose the **lowest rung that meets it** (`references/method_ladder.md`): rules, then statistics, then ml; add genai when language is involved.
   - Mark it `out_of_scope` when it needs a method above the policy, points that are not in the list and cannot be substituted, or a third-party platform. Out-of-scope items need only `ref`, `title`, `verdict`; add a one-line `reason` (method above policy, which points are missing, third-party platform).
   - For applicable items, reference points **only** by `id` and `name` exactly as they appear in `points.json`. Prefer the points from `candidates.json`.
   - Write the logic as short steps; label every threshold as an example to confirm.
   - Give one example output with illustrative values, and the output's shape (tags, queue item, report).
   - Put anything needed but absent from the list in `missing` (e.g. fan power, floor area, emission factor).

4. **Validate** — must pass before reporting:
   `python scripts/validate.py assessment.json points.json --max-method <policy>`
   Fix every error (unknown id, wrong name, method above policy) and rerun.

5. **Build the report**
   `python scripts/build_report.py assessment.json points.json --out PointProof_report.xlsx`
   One sheet: applicable items with points, logic and example output; out of scope; missing data; points used per system; optional architecture.

## Rules

- Never cite a point that is not in `points.json`. If the right point is missing, say so in `missing` or move the item out of scope.
- Call statistics "statistics", not "AI model". Use ML only when a trained, retrained model is genuinely needed.
- Recommendations that change a setpoint or create a work order always go through operator approval; say so in the logic.
- Keep client documents out of anything you publish.

## Reply to the user

After the report is built: the counts (applicable / out of scope), the two or three most important gaps from `missing`, and the report file. Do not repeat the whole table in chat.
