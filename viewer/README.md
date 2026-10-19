# Vessim Viewer

One interface for the local CLI, exported reports and the documentation gallery.
Python defines and runs scenarios. The viewer analyzes completed simulation results;
it does not monitor live systems, execute scenarios, or implement an optimizer.

## Open results

```sh
vessim view results/study.json
vessim view results/run
vessim view results/collection
vessim view results/studies
vessim view results/study.json --export report
python -m http.server --directory report
```

The input can be an experiment JSON/directory, a directory of experiment directories,
a grouped study JSON/directory, or a directory of study directories. When a directory
contains `study.json`, its explicit grouping takes precedence over discovery. A collection
of experiments gives each run its own configuration; grouping is never guessed from
parameters. A collection of studies enables the study selector.

Only completed runs appear in the analysis. Invalid, failed, interrupted and missing
records produce data issues without preventing valid runs from loading. Missing
recordings are reported when charts are opened; summary-only results are supported.

## Formats and reference origins

`vessim.experiment` **v1** is the canonical experiment record. The only supported study
format is `vessim.study` **v2**, a thin index:

```json
{
  "format": "vessim.study",
  "schema_version": 2,
  "study_id": "dispatch",
  "name": "Dispatch comparison",
  "run_parameters": ["seed"],
  "configurations": [
    {
      "configuration_id": "self-consumption",
      "name": "Self consumption",
      "runs": [
        {"path": "runs/seed-41/experiment.json"},
        {"path": "runs/seed-42/experiment.json"}
      ]
    }
  ]
}
```

Names and descriptions are optional; IDs are stable, nonempty strings. Run IDs must
be unique within a study, and configuration IDs must be unique. Study references are
relative to the study JSON, including references to experiments outside its directory.
CSV references are relative to the experiment JSON and must stay within its directory.
The server exposes only registered summaries and trajectories, not arbitrary input files.
The experiment schema supports a CSV path or null, not inline trajectory arrays.

`run_parameters` identifies realization inputs such as seeds; remaining inputs shared
within a configuration are derived from the experiment records. No inputs or result
metrics are copied into the study index. Summary metrics, units, descriptions and
assumptions remain authoritative. There is no support for the older embedded-study
format or the retired viewer.

For large summary-only studies, a configuration may use `run_batch` instead of `runs`.
The referenced `vessim.viewer.run-batch` v1 JSON contains `shared` experiment fields and
an array of `runs` overriding those fields. Parameters are merged by key. Each expanded
record is validated as a canonical experiment; execution, metrics and definitions are
preserved. Batch references are relative to the study; any batch recording references
are relative to the batch. See `examples/monte_carlo_replay.py` for a runnable producer.

## Analysis workflow

- **Results:** searchable, sortable, paginated table; selected-first sorting; column
  selection/reordering and display units; selection-linked plots; selected/filtered CSV.
- **Repeated runs:** individual runs or configuration summaries, selectable statistic
  and range/IQR. Distribution, trade-off and empirical-distribution plots; optional faint
  runs and a selectable Pareto front. Fronts describe the displayed metrics and selected
  minimize/maximize directions; they are not an optimization engine.
- **Details:** configuration inputs, realization inputs, grouped metrics with recorded
  descriptions and assumptions, actor metrics, and simulation settings.
- **Time series:** select runs/configurations, overlay compatible signals, choose
  elapsed or UTC alignment, reorder charts, customize colors, and synchronize zoom.

Single-microgrid studies combine run and microgrid metrics under Energy, Cost, Carbon,
then Other results. Multiple microgrids retain Whole-system results and each microgrid's
results. These headings do not change recorded scope or units. Fixed seeds belong under
Simulation settings; varying seeds remain Run inputs. Integer inputs have no decimals;
metric columns normally have two, with extra precision for tiny quantities. Decimal
alignment is consistent, missing values are not zero, and exports retain full precision.
Currency is recorded per metric; the viewer does not perform currency conversion.

Only Results and Time series are navigation destinations. There is no separate Compare
page, baseline role, scenario editor, or live dashboard. Prometheus/Grafana handle live
monitoring; Optuna handles optimization and its search history. Hydra is a project choice.

## Performance and limits

Catalog discovery reads experiment summaries without opening CSVs. The browser fetches
only the active study's summaries. Tables render 50 rows per page. Large scatter plots
show at most 10,000 sampled points; the table and CSV retain all runs. Configuration
plots show at most 50 configurations; empirical distributions show at most 12.

CSV parsing takes place in a worker. Signals through 10,000 samples are retained in full;
larger signals use extrema-preserving reduction. Zoom does not fetch finer samples.
Repeated-run trajectory summaries require identical timestamps after alignment and
unreduced recordings; no interpolation or missing-value imputation occurs. Bands are
observed ranges/IQR, not confidence intervals. Pointwise aggregate curves may not be
physically realizable runs. Outcome summaries always use recorded metrics.

The catalog currently indexes all supplied studies in server memory; it is not a
persistent query service. The browser also holds all summaries for the active study.

## Development and validation

```sh
npm --prefix viewer ci
npm --prefix viewer run build
npm --prefix viewer run lint
npm --prefix viewer test
.venv/bin/python -m pytest tests/test_viewer.py tests/test_docs_viewer.py
.venv/bin/python viewer/tests/prepare.py
cd viewer && npx playwright test
```

`src/` contains the React interface and the independent analysis modules.
`components/controls.jsx` defines shared selects, multi-choice menus, and unit controls.
Field selectors and column menus use the same ordering from `columnGroups()`.
`Chart` manages ECharts instances and their cleanup, while plot calculations stay outside React.
`view-link.js` owns the versioned sharing format and validates links against the loaded study.
Keep its v1 field names stable and retain the saved-link regression tests when changing view state.

`build.mjs` uses Vite to bundle React and the recording worker with relative asset URLs.
ECharts and dependency licenses are included in `vessim/_viewer_dist` alongside the bundle.
The same files ship in the Python wheel, exported reports, and documentation gallery.
Users do not need Node installed.
Rebuild after frontend edits, then run `vessim view`.

Browser tests start CLI and static-export servers on ports 8721/8722 and exercise both
interfaces, repeated runs, multi-microgrid groups, missing recordings and 10,000 summary
runs. `tests/prepare.py` creates a deterministic fixture in `results/viewer-release`.
Screenshots and timings are recorded there. Python tests cover reference origins,
partial data, duplicate identities, batches and exports.

## Recorded examples and documentation

```sh
python viewer/design/build_studies.py --trials 100 --workers 8
python viewer/export_docs.py
python -m http.server --directory docs
```

The example builder preserves existing recorded results. The documentation exporter
uses the same Catalog and packaged assets as the CLI, and validates all references
before replacing generated output. It includes Getting started, Equipment comparison,
Optuna search, Probabilistic sampling, Multiple microgrids, and Optuna 2 when its batch
study is available. Optuna is optional and is not a core Vessim dependency.

To inspect optimization trials, associate each trial with its saved experiment path
and Vessim run ID, then open the resulting study here. Use Optuna Dashboard for optimizer
history and diagnostics. `examples/infrastructure_study.py --financial --trials 100`
provides the annual cost/emissions example with recorded financial assumptions.
