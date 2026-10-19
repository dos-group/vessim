# Optimization

Simulation studies can span more configurations than you can reasonably test.
Often, you want to find designs that are cost-effective, low-carbon, or resilient, and understand the trade-offs between those goals.

Vessim lets you evaluate candidate designs with your own demand profiles, energy infrastructure, and control strategies.
Connect those simulations to an optimizer such as [Optuna](https://optuna.org/) to search for promising designs using the [metrics](results.md) that matter to your study.

## Size a battery

Suppose your datacenter has solar generation and you are choosing a battery.
More storage can reduce grid imports by saving surplus solar power for later, but it also costs more.
Rather than choosing a single weighting between these goals, we can search for designs that offer different trade-offs.

This example uses a synthetic solar profile and searches battery capacities between 0.5 and 5 kWh.
It minimizes both battery purchase cost and grid imports over the six-hour scenario.
Install Optuna with `pip install optuna`.

```python
import optuna
import pandas as pd
import vessim as vs

solar = vs.Trace(pd.Series(
    [0, 1200, 2400, 1200, 0, 0, 0],
    index=[hour * 3600 for hour in range(7)],
))


def objective(trial):
    capacity = trial.suggest_float("battery_capacity_wh", 500, 5000)
    with vs.Environment("2026-01-01", step_size=1800) as env:
        env.add_microgrid(
            name="site",
            actors=[vs.Consumer("load", 700), vs.Producer("solar", solar)],
            dispatchables=[vs.SimpleBattery("battery", capacity), vs.GridConnection()],
        )
        recorder = env.add_controller(vs.Recorder(timeseries=False))
        env.run(6 * 3600)

    battery_cost = capacity / 1000 * 300  # Illustrative purchase cost in EUR/kWh
    grid_import = recorder.metrics["microgrids"]["site"]["grid_import"]
    return battery_cost, grid_import


study = optuna.create_study(
    directions=["minimize", "minimize"],
    sampler=optuna.samplers.NSGAIISampler(seed=42),
)
study.optimize(objective, n_trials=20)

for trial in study.best_trials:
    print(trial.params, trial.values)
```

Optuna proposes a capacity, Vessim simulates it, and the objective function returns its cost and grid imports.
`study.best_trials` contains the Pareto front among the evaluated designs.
None of these designs improves one objective without worsening the other.
You can choose a candidate based on your budget or import target.

## Explore your design choices

The same approach can search renewable capacity, generator sizing, or dispatch policy parameters.
Use cost and emissions metrics as objectives, or assess resilience by simulating outages.
To account for uncertain demand or weather, evaluate each candidate across several scenarios and compare its average or worst-case performance.

The [complete infrastructure example](https://github.com/dos-group/vessim/blob/main/examples/infrastructure_study.py) searches wind, solar, and battery sizes over a full year and records each candidate's results.
Its `--financial` mode compares annual cost with grid-import emissions using illustrative inputs.
After following the [example setup instructions](https://github.com/dos-group/vessim/blob/main/examples/README.md), run:

```console
python examples/infrastructure_study.py --financial --trials 100 --output results/infrastructure-search
python -m vessim view results/infrastructure-search
```

Explore the [annual optimization results](../viewer/index.html?study=optuna-search#results) from 100 equipment configurations in the viewer.

Use [Optuna Dashboard](https://optuna-dashboard.readthedocs.io/en/stable/) to explore the search and its trade-offs, then inspect saved runs in the [Vessim viewer](../vessim_viewer.md) to understand why a design performs well.
See Optuna's [multi-objective tutorial](https://optuna.readthedocs.io/en/stable/tutorial/20_recipes/002_multi_objective.html) for more on configuring the search.
