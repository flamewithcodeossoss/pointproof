# The method ladder

PointProof always picks the **simplest method that meets the requirement**, in this order:

| Rung | Method | Use it when | Typical examples |
|---|---|---|---|
| 1 | `rules` | A fixed comparison or arithmetic answers it | Running outside schedule, fault energy cost, ROI, setpoint trim-and-respond |
| 2 | `statistics` | It needs a fitted equation, a percentile, a median or a running sum, but no training pipeline | Degree-day baselines, CUSUM drift, benchmarking, alarm KPIs, minimum night flow |
| 3 | `optimisation` | The answer is a **decision** under constraints: a schedule, a route, an assignment, an order quantity, a selection within a budget | Technician scheduling, collection routing, work-order assignment, reorder points, retrofit selection under a budget |
| 4 | `ml` | Accuracy depends on a trained model that must be retrained and monitored | Demand forecasting, remaining useful life, learned anomaly models |
| + | `genai` | Language is involved: questions, explanations, summaries, text classification | Copilot, incident reports, explaining a recommendation |

`genai` is not a rung: it is added on top of whichever rung computes the numbers.

## How to decide

1. Can an engineer write it as `if … then …` or a formula? → `rules`.
2. Does it need a fitted line, an average, a median, a percentile, a control chart? → `statistics`.
3. Is the output a choice among many combinations, with limits (people, hours, trucks, budget, capacity)? → `optimisation`. Inputs often come from rungs 1–2 (e.g. a fill rate feeds a routing model).
4. Would a wrong number be judged by forecast error or model accuracy, and does it need retraining? → `ml`.
5. Does someone read or write text? → add `genai`.

Optimisation is deterministic: the same inputs give the same plan, and the solver reports why (binding constraints, objective value). It needs no training data, only the constraints from master data.

## Policy

Pass `--max-method` to `validate.py` to enforce a team policy:

- `--max-method statistics` — no optimisation and no ML.
- `--max-method optimisation` — a team that delivers rules, statistics and OR, but not ML.
- `--max-method ml` (default) — no limit.

## Honest labels

- Call a regression baseline "statistics", and a solver "optimisation", not "AI model".
- Thresholds and constraint values are **examples** until the owner confirms them.
- Example outputs use **illustrative values**.
