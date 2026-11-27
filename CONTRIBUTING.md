# Contributing to PointProof

Thank you for your interest in contributing to PointProof! We welcome contributions from building automation engineers, energy analysts, controls specialists, and AI developers.

## Ways to Contribute

1. **Adding Standard Use Cases** to the domain files in `skills/pointproof/references/usecases/`
2. **Improving Parsers and Readers** for points sources (CSV, XLSX, PDF, tag exports, BACnet EDE, Brick, Haystack, OPC UA)
3. **Enhancing Outputs** (the Excel report, PointProof Studio, export formats)
4. **Expanding Test Coverage** in `tests/test_pointproof.py`
5. **Documentation & Guides** (Architecture explanations, standard references, case studies)

---

## Adding a New Use Case

The most valuable contribution is expanding the use-case library: add your use case to the right domain file in `skills/pointproof/references/usecases/` (`buildings`, `water`, `utilities`, `industrial`, `datacentres`, or `general` for anything that applies to every site):

```yaml
  - id: custom-usecase-id
    title: Short Descriptive Title
    method: [rules]                 # Pick simplest: rules, statistics, optimisation, ml (+ genai)
    standards: [ASHRAE Standard X]  # Optional international standard reference
    why: Concise technical justification of why this method suffices.
    solver: scripts/optimise/schedule_maintenance.py   # optimisation only: the reference model
    slots:
      - key: primary_sensor
        label: Plain English Sensor Label
        required: true
        match:
          name: [regex_pattern_1, '\bshort\b'] # `_` matches any separator; single-quote \b patterns
          units: ['[km]?w']         # optional: whole units value, e.g. kW
          equipment: [chiller, ahu] # optional equipment filter
          exclude: [bypass]         # optional exclusion filter
      - key: setpoint_control
        label: Writable setpoint
        required: true
        writable: true              # Requires R/W permission
    logic:
      - Step 1 description.
      - Step 2 description.
    output: Description of output tags or alerts.
    runs: Continuous / Daily / Monthly
    history: Minimum historical data required
```

### Guidelines for Use Cases:
- **Strict Method Ladder**: Always pick the lowest rung that meets the requirement (Rules < Statistics < Optimisation < ML).
- **Vendor-Neutral Patterns**: Use common naming conventions (e.g. DBO, Brick Schema, Project Haystack, standard BACnet object names). Names are normalised first (accents dropped, camelCase split, abbreviations such as SAT, CHWST, SP and kW expanded) and compared as lower-case words, so write `run_status` once rather than every spelling, and wrap short tokens in word boundaries (`'\bkw\b'`) so they do not match inside longer words. If your pattern relies on a new abbreviation, add it to `scripts/textnorm.py` and to the studio template.
- **Domain Packs**: Private or experimental use cases can live in their own YAML file and be loaded with `match_usecases.py --library pack.yaml --add-builtin`.
- **Anonymity**: Never include proprietary, sensitive, or client-specific point names or data.
- **Required vs Optional**: Clearly distinguish mandatory telemetry from nice-to-have inputs.

---

## Development & Testing Workflow

### 1. Prerequisites
- Python 3.9+
- Git

### 2. Setup
```bash
git clone https://github.com/flamewithcodeossoss/pointproof.git
cd pointproof
pip install -r requirements.txt
```

### 3. Run the Test Suite
Before submitting any changes, ensure all tests pass:
```bash
pytest -v
```

### 4. Code Standards
- Keep scripts lean, dependency-light, and fast.
- New point readers go in `scripts/adapters.py`, with a small fictional sample in `examples/formats/` and a test.
- Matching rules live in two places, `scripts/match_usecases.py` and the studio template (`assets/studio_template.html`); change both together.
- Ensure all file path outputs automatically create missing parent directories.
- Maintain backward compatibility with existing `assessment.json` and `points.json` schemas.

---

## Pull Request Guidelines

1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/my-new-usecase
   ```
2. Commit your changes with a clear commit message:
   ```bash
   git commit -m "Add use case: AHU supply air temperature reset"
   ```
3. Push to your fork and submit a Pull Request to `flamewithcodeossoss/pointproof`.
4. Ensure GitHub Actions CI passes on your PR.
