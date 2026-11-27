---
name: pointproof
description: Prove which AI use cases a site can really deliver from its points list, for buildings, water networks, utilities, industrial plants and data centres. Reads any points source (CSV/Excel/PDF lists, historian or PI tag exports, BACnet EDE, Brick, Project Haystack, OPC UA NodeSet). For each requirement it picks the simplest method (rules, statistics, optimisation, ML, plus GenAI), lists the exact points it needs, flags missing data, validates every point, and builds an interactive studio and an Excel report. Use when given a points, I/O or tag list plus AI requirements, use cases, a tender or an RFP to scope.
---

# PointProof

Turn "we need AI for X" into a decision you can defend point by point: applicable or out of scope, the simplest method, the exact points from the client's own list, the logic and the output. Every point is checked against the points list, so nothing is invented.

## Inputs

1. **Points source**, any of: CSV/TSV (any delimiter, UTF-8 or Windows-1252), XLSX or PDF table; historian / PI / SCADA tag export; BACnet EDE (`.csv`); Brick model (`.ttl`); Project Haystack JSON (grid or Hayson); OPC UA NodeSet2 (`.xml`). Any naming style and language works.
2. **Requirements**: the AI use cases to assess (a list, a table, or tender text). Give each a short `ref`.
3. **Policy**: the highest method the team delivers: `rules`, `statistics`, `optimisation` or `ml`.
4. Optional: **domain** (buildings, water, utilities, industrial, datacentres) and **capacity** (how many items the team can take).

If anything is missing, follow `references/interview.md`: one round of at most four questions, sensible defaults, then work.

## Workflow

Scripts are in `scripts/` next to this file. Python 3.9+: `pip install openpyxl pyyaml` (add `rdflib` for Brick, `pdfplumber` for PDF, `ortools` for the optimisation examples).

1. **Parse the points**
   `python scripts/parse_points.py <file> --out points.json` (format is detected; force it with `--format table|brick|haystack|ede|opcua`).
   Check the summary and any WARN lines. For tables, if a column was missed or the wrong one was taken, rerun with `--map name="<Header>"` (fields: id, system, equipment, description, name, rw, units, asset). For a workbook it picks the sheet with the best header; use `--sheet` to choose another. If ids repeat (numbering restarts per panel), points get ids like `12-2`; map a unique column to `id` if there is one.

2. **Match the library**
   `python scripts/match_usecases.py points.json --domain <domains> --out candidates.json`
   Lists which library use cases (`references/usecases/*.yaml`) the points support: ready, partial or blocked, and the points that fill each slot. Names are normalised first, so `AHU01.SATSP`, `Supply Air Temp SP` and a Brick or Haystack name all match, and units count too (a `kWh` point fills an energy slot even with a cryptic tag). Without `--domain`, all domains are matched; `general` holds checks that apply to any site. For a domain the library lacks, add a pack with `--library pack.yaml --add-builtin`, or reason from first principles in step 3.

3. **Assess each requirement** and write `assessment.json` per `references/assessment_schema.md`:
   - Map it to a library use case when one fits; otherwise reason from first principles.
   - Choose the **lowest rung that meets it** (`references/method_ladder.md`): rules, statistics, optimisation, ml; add genai when language is involved.
   - Mark it `out_of_scope` when it needs a method above the policy, points that are not in the list and cannot be substituted, or a third-party platform. Out-of-scope items need only `ref`, `title`, `verdict`; add a one-line `reason` (method above policy, which points are missing, third-party platform).
   - Reference points **only** by `id` and `name` exactly as in `points.json`, preferring those in `candidates.json`. A slot marked `writable_unverified` (its points have no R/W data, listed in `writable_unknown_ids`) goes in `missing` as "confirm the point is writable".
   - Write the logic as short steps; label every threshold as an example to confirm. Give one example output with illustrative values.
   - For optimisation items, name the model (assignment, routing, knapsack, inventory) and its constraints. `scripts/optimise/` has a runnable reference model for each; run one on example data to produce a realistic example output.
   - Set `group` (e.g. Energy, Maintenance, Network losses) so coverage can be shown per group.
   - Put anything needed but absent in `missing` (e.g. fan power, floor area, tariff, technician skills).

4. **Validate**: must pass before anything is shown as final.
   `python scripts/validate.py assessment.json points.json --max-method <policy>`
   Fix every error (unknown id, wrong name, method above policy) and rerun.

5. **Review with the user**: show the shortlist table and counts (see `references/interview.md`), ask what to move in or out, apply, revalidate.

6. **Build the outputs** the user wants:
   - Studio: `python scripts/build_studio.py --assessment assessment.json --points points.json --out studio.html`
     One HTML file. The user toggles items in or out, changes the policy and capacity, edits points and logic, adds library use cases, imports new points files, and sees coverage, the method ladder, an architecture diagram and gaps update live. It exports `assessment.json` (feed it back to step 4), Excel, CSV, a PDF report, or the studio with changes. Publish or send it as the user prefers.
   - Excel: `python scripts/build_report.py assessment.json points.json --out PointProof_report.xlsx` (one sheet).
   If the user edited in the studio, take the exported `assessment.json`, validate it again, then rebuild.

## Rules

- Never cite a point that is not in `points.json`. If the right point is missing, say so in `missing` or move the item out of scope.
- Call statistics "statistics" and solvers "optimisation", never "AI model". Use ML only when a trained, retrained model is genuinely needed.
- Recommendations that change a setpoint, a schedule or create a work order go through operator approval; say so in the logic.
- Keep client documents and client names out of anything published as an example.

## Reply to the user

After the outputs are built: the counts (applicable / out of scope, coverage %), the two or three most important gaps, and the files. Do not repeat the whole table in chat.
