# Contributing to PointProof

Thank you for your interest in contributing to PointProof! We welcome contributions from building automation engineers, energy analysts, controls specialists, and AI developers.

## Ways to Contribute

1. **Adding Standard Use Cases** to `skills/pointproof/references/usecases.yaml`
2. **Improving Parsers** for diverse BMS / SCADA points list formats (CSV, XLSX, PDF)
3. **Enhancing Reporting** (Excel layouts, formulas, styling, or export formats)
4. **Expanding Test Coverage** in `tests/test_pointproof.py`
5. **Documentation & Guides** (Architecture explanations, standard references, case studies)

---

## Adding a New Use Case

The most valuable contribution is expanding the standard use-case library in `skills/pointproof/references/usecases.yaml`:

```yaml
  - id: custom-usecase-id
    title: Short Descriptive Title
    method: [rules]                 # Pick simplest: rules, statistics, ml (+ genai)
    standards: [ASHRAE Standard X]  # Optional international standard reference
    why: Concise technical justification of why this method suffices.
    slots:
      - key: primary_sensor
        label: Plain English Sensor Label
        required: true
        match:
          name: [regex_pattern_1, regex_pattern_2]
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
- **Strict Method Ladder**: Always pick the lowest rung that solves the physics (Rules < Statistics < ML).
- **Vendor-Neutral Patterns**: Use common naming conventions (e.g. DBO, Brick Schema, Project Haystack, standard BACnet object names).
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
