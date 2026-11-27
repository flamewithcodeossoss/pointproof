# Learn operations research with PointProof

The `optimisation` rung is where a requirement asks for a **decision under constraints**: a schedule, a route, an order quantity, a choice within a budget. Each script in `skills/pointproof/scripts/optimise/` is a small, complete OR model on fictional data. Read it, run it, then change one constraint and watch the answer move.

| Script | Building question | OR model | Concepts to learn |
|---|---|---|---|
| `reorder.py` | When do we reorder towels and soap, and how many? | Inventory (s, Q) policy | Safety stock, service level, EOQ |
| `budget_select.py` | Which retrofits do we fund with 2 M? | 0/1 knapsack (integer programming) | Binary variables, budget constraint, exclusive choices |
| `schedule_maintenance.py` | Who fixes what, and which day? | Assignment + capacity (CP-SAT) | Decision variables, hard vs soft constraints, penalties |
| `route_collection.py` | Which bins are due tomorrow, and in what order? | Capacitated vehicle routing (CVRP) | Distance matrix, capacity dimension, metaheuristics |

```bash
O=skills/pointproof/scripts/optimise; E=examples/or
python $O/reorder.py $E/consumables.csv
python $O/budget_select.py $E/retrofits.csv --budget 2000000
python $O/schedule_maintenance.py $E/maintenance_plan.json
python $O/route_collection.py $E/bins.csv --vehicles 2 --vehicle-capacity 4000
```

## Exercises

1. **Reorder**: raise the service level to 0.99. How much does safety stock grow? Why is the growth not linear?
2. **Budget**: switch `--objective co2`. Does the selection change? Add a minimum-saving constraint per project.
3. **Scheduling**: give T3 the `hvac` skill, or cut `days` to 2. Which tasks drop out, and why those?
4. **Routing**: lower `--vehicle-capacity` until the solver needs a third truck. Add time windows (OR-Tools VRPTW).
5. **Combine rungs**: compute `fill_rate_pct_per_day` from bin history with a weekday average (statistics), then feed it to the router (optimisation).

## Where to learn more

- **Modelling basics**: *Operations Research (1): Models and Applications*, National Taiwan University (Coursera): LP, integer and nonlinear programming.
- **Python, hands-on**: *Hands-On Mathematical Optimization with Python* (Cambridge University Press, 2025); companion notebooks at mobook.github.io.
- **Solvers**: Google OR-Tools guides and examples: routing (VRP, time windows), CP-SAT scheduling, assignment, packing.
- **Textbook reference**: Hamdy A. Taha, *Operations Research: An Introduction*.
