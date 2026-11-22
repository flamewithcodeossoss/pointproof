# The method ladder

PointProof always picks the **simplest method that meets the requirement**, in this order:

| Rung | Method | Use it when | Typical examples |
|---|---|---|---|
| 1 | `rules` | A fixed comparison or arithmetic answers it | Running outside schedule, fault energy cost, ROI, setpoint trim-and-respond |
| 2 | `statistics` | It needs a fitted equation, a percentile, a median or a running sum, but no training pipeline | Degree-day baselines, CUSUM drift, benchmarking, alarm KPIs |
| 3 | `ml` | Accuracy depends on a trained model that must be retrained and monitored | Demand forecasting, remaining useful life, learned anomaly models |
| + | `genai` | Language is involved: questions, explanations, summaries, text classification | Copilot, incident reports, explaining a recommendation |

`genai` is not a rung: it is added on top of whichever rung computes the numbers.

## How to decide

1. Can an engineer write it as `if … then …` or a formula? → `rules`.
2. Does it need a fitted line, an average, a median, a percentile, a control chart? → `statistics`.
3. Would a wrong number be judged by forecast error or model accuracy, and does it need retraining? → `ml`.
4. Does someone read or write text? → add `genai`.

## Policy

Pass `--max-method` to `validate.py` to enforce a team policy:

- `--max-method statistics` — a team that does not deliver ML: any applicable item marked `ml` fails validation. Mark it `out_of_scope` instead.
- `--max-method ml` (default) — no limit.

## Honest labels

- Call a regression baseline "statistics", not "AI model".
- Thresholds in the logic are **examples** until the owner confirms them.
- Example outputs use **illustrative values**.
