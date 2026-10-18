# Viewer validation and performance

The current design target is [simulation studies only](https://github.com/dos-group/vessim/blob/main/viewer/README.md#agreed-design-scope--2026-10-17), with completed simulation results and no live-recording analysis.
The prototype now filters incomplete runs and removes status controls.
Earlier production validation below still describes status/incomplete-run behavior that predates this decision.

The study workspace was validated locally on macOS with Node 25.9, Python 3.13, React 19, ECharts 5, and headless Google Chrome.
Numbers below are a reproducible local smoke benchmark, not a cross-machine latency guarantee.

## Four-study preview validation (2026-10-17)

### Repeated-run visualization follow-up (2026-10-18)

The study now titled **Probabilistic sampling** exercises three configurations with five seeds each.
Results controls sit beside the plot/table; configuration dots, summary markers, observed/IQR ranges and expandable rows share one display mode.
Time series offers configuration summaries, spread bands and individual curves.
The browser gallery check verifies 15 recorded points, three summary markers, three trajectory summaries/bands, all 15 individual curves, mean values against CSV samples, and desktop/mobile layouts.
DOM-free tests cover missing values, negative/cross-zero ranges, quantiles, mismatched timestamp grids and rejection of reduced recordings.
No interpolation or confidence-interval estimation occurs.
The follow-up browser checks cover real wheel zoom, reset and preservation on rerender, adjacent trade-off axis controls, faint-point toggling, and decimal alignment measured from rendered table text.
Twenty-one model, unit, formatting and uncertainty tests pass; the gallery and results browser checks and frontend lint pass.
Desktop and 390px screenshots were inspected.
The topic-grouping follow-up verifies shared seeds under Simulation settings, varying seeds under Run inputs, merged single-microgrid Energy/Cost/Carbon groups, and separate whole-system/microgrid scopes for multi-microgrid studies.
The recorded metric identities and units are preserved.
Browser checks cover the Columns menu and inspector; lint and build pass (the existing bundle-size warning remains).

The gallery was subsequently extended to five studies: **Getting started** is first, and **Annual sizing** is now displayed as **Equipment comparison** (its stable study ID remains unchanged).
The new entry executes `basic_example.py` unchanged in an isolated directory and reproduces the tutorial's 26.71 kWh import and 11.08 kWh export.
Its recording has 864 five-minute observations across three days, using the Berlin column of the bundled solar CSV.
The browser gallery check covers the new default, metric columns, trajectories and mobile layout; a single-run study initially hides the outcome scatter plot.

Signal-menu follow-up: the Grid balance category was removed.
Net actor power appears first under Actors; grid-connection power appears under Dispatchables.
The aggregate is hidden only when each selected recording has an identified, recorded single-connection replacement.
Both battery models now record `current_power`.
The 105 battery-equipped gallery trajectories were regenerated from their original parameters and seeds; all summary metrics matched exactly, and existing CSV columns matched within numerical tolerance before publication.
Original CSVs were backed up under `/private/tmp/vessim-power-recordings-elpvaxq1/originals`.
The follow-up passed 144 Python tests across battery, microgrid, recording and example behavior, plus 13 prototype model/unit tests and frontend lint.

The active `viewer/design/` gallery now has four studies, in order: Annual sizing (8 annual runs), Optuna search (100 annual runs), Dispatch comparison (3 strategies with 5 seeds each), and Multiple microgrids (3 weekly runs, each with 3 microgrids).
The first three have one microgrid.
Earlier fixture and 24-trial reports below are historical checks, not additional examples in the normal selector.

Reproduce with `python viewer/design/build_studies.py --trials 100`, serve the repository root on port 8715, and start Optuna Dashboard on port 8091 using `results/viewer-gallery/optuna-search/optuna.db`.
Then run `node viewer/design/gallery-check.cjs`.
The initial generation took 70.25 seconds locally, reusing the existing eight annual sizing recordings.
Search summaries total 935,691 bytes; their CSV trajectories total 161,403,094 bytes.

Chrome at 1440 × 1000 measured 197–206 ms from navigation to the default table and 96–111 ms to switch to the 100-run search.
Only 50 table rows render at once, and all 100 points are available in the scatter plot.
No CSV is requested while browsing summaries.
Annual overlays retain all 8,760 samples per series.
These are local smoke measurements, not production performance guarantees.

The browser check exercises study switching, pagination, selected-first sorting, selected CSV export, financial metric inspection, repeated-run summaries and individual runs, single/multiple-microgrid signal menus, and overlays.
Screenshots at desktop and 390 × 844 mobile sizes were inspected; horizontal table scrolling stays inside the table.
Optuna Dashboard's 100-trial Pareto view was also opened.
Screenshots and timings are under `results/viewer-gallery/validation/`.

Validation includes 67 Python tests for scenarios, results and experiment files; 9 prototype model tests; 13 production frontend data tests; Ruff, frontend lint and production build.
The build retains the existing large-bundle warning (825 kB minified main chunk).
Dedicated result-table, chart-order/color and stale-cache browser checks also passed.
An audit checked all 100 trial identities and objective values against their saved metrics, plus completion and microgrid counts for all dispatch and multiple-microgrid records.

Financial calculations are checked against trajectory integrals.
The coincident multi-microgrid peak is checked against simultaneous CSV states, rather than summing separate peaks.
Costs and inputs are synthetic; the example excludes power-rating premiums, financing, maintenance and taxes.
Multi-microgrid sites are independent.
The preview's grouped v2 indexes have not yet been migrated to the packaged viewer; canonical experiment records remain v1.

## Fixtures and measured behavior

The grouped preview has a separate, deterministic indexing benchmark: `node viewer/design/benchmark.mjs 10000`.
It creates 10,000 single-run configurations, two parameters and two custom metrics, without trajectories.
Replacing a per-configuration scan of all runs with one membership pass reduced four local indexing measurements from 193–435 ms to 48–52 ms.
This measures `indexStudy` only; it excludes loading, browser rendering and plotting.
Membership and ordering are covered by the prototype model tests.

`python -m benchmarks.viewer_fixture --runs 10000` produces an 8.59 MB study JSON with deterministic synthetic values (seed 42), three parameters, four scoped metric fields, explicit nulls, and a mix of completed and failed runs.
These are performance fixtures, not scientific simulation results.
The fixture has no trajectories.

Serve it with `python -m vessim view results/viewer-benchmark.json --no-browser -p 8712`.
The browser suite measures navigation through the first visible 50-row table and searching for `scenario-09999`.

| Measurement | Observed across local validation runs |
|---|---:|
| Navigation to usable 10,000-run table | 0.46–0.57 s |
| Fetch, parse, and index catalog | 0.26–0.27 s |
| Search to a single matching row | 63–83 ms |
| Rendered table body rows | 50 |
| Total document elements | approximately 1,050 |
| Browser JS heap (GC-dependent snapshot) | approximately 44–79 MB |
| Trajectory requests while exploring summaries | 0 |

Catalog responses use gzip when supported.
Table rendering is paginated.
Scatter plots display at most 10,000 regularly sampled points plus selected runs.
Selected runs remain represented in the plot even when they fall outside the overview sample.
The viewer indexes metadata in browser memory; extremely large or wide studies may need a future query-backed catalog.
There is no claim of unbounded browser scaling.

Large CSV trajectories are fetched and parsed in a dedicated worker.
Each signal is reduced to at most 4,000 overview points, preserving bucket extrema, representative explicit gaps, and endpoints.
A 100,000-point test checks a narrow peak, a null gap, and both endpoints.
Zoom operates on this overview; original data can be downloaded for exact analysis.
The worker still holds the full input and intermediate series while parsing.
Concurrent comparison is limited to eight runs.

## Workflow checks

`examples/strategy_comparison.py` executes 12 actual Vessim simulations: three illustrative policies and four battery capacities, with identical exogenous inputs.
It writes individual experiment directories; the viewer discovers these from the parent directory without duplicating records in a study file.
The browser checks cover:

- Selection, selected-row export, baseline changes, and configuration differences.
- No trajectory fetch until inspection or overlays are requested.
- Compatible overlays with elapsed and UTC time alignment.
- Summary-only results, custom CSV fields, missing CSVs, and partial catalogs.
- Filtering, paging, and bounded rendering of 10,000 runs.
- Desktop (1440 px), tablet (900 px), and phone (390 px), including horizontal overflow.
- Light/dark appearance and static exports under a URL subdirectory.

Screenshots and the latest measurement JSON are generated under `results/viewer-validation/`.
Run instructions are in [viewer/README.md](https://github.com/dos-group/vessim/blob/main/viewer/README.md).

Python tests cover all input forms, relative artifact origins, nonfinite JSON, unsupported formats, lazy CSV artifacts, duplicate IDs, and static exports.
Regression tests also cover shared reader validation, CSV relocation, escaped state paths, string identifiers, post-run scalar metrics, and cleanup failure status.
Frontend data tests cover scoped metrics, incompatible units/assumptions, missing values, zero baselines, spreadsheet-safe CSV, timezone handling, and chart reduction.

## Optuna Dashboard evaluation

The optional example was executed with Optuna 5.0.0 and Optuna Dashboard 0.21.0, using eight sequential trials and recorded trajectories.
The actual dashboard showed a two-objective Pareto front, per-objective history, trial parameters, hyperparameter-importance panels, execution timeline, and a list of best trials.
Trial details exposed `vessim_run_id`, `vessim_experiment`, and `vessim_viewer` attributes.
The viewer URL is presented as a user-attribute value; this is not a custom embedded Vessim panel in Optuna Dashboard.

This supports keeping optimization-specific analysis in Optuna Dashboard and using Vessim for detailed simulation evidence and ordinary scenario comparisons.
An eight-trial smoke study validates the integration, not optimizer convergence or the statistical reliability of displayed parameter importance.

To repeat the optional browser check, run the example and dashboard, then set `OPTUNA_DASHBOARD_URL=http://localhost:8089` when invoking Playwright.
The check opens the recorded Vessim viewer URL; serve that result collection at the URL provided to the example, or set `VIEWER_OPTUNA_URL` to override its origin.
`VIEWER_STATIC_URL` enables the static-export browser check.
These integration checks are optional so normal viewer tests do not require Optuna.

## Deliberate limits

### Annual infrastructure prototype validation (2026-10-17)

The separate `viewer/design/` prototype now includes actual annual recordings from `examples/infrastructure_study.py`: eight named setups and 24 Optuna trials (23 distinct configurations), each with 8,760 hourly intervals.
Every record completed 31,536,000 simulated seconds.
The fixed sweep took 3.95 s; the search, including SQLite persistence and CSV recording, took 13.52 s on the local development machine.
CSV sizes were 10.96 MB and 34.41 MB respectively.
These timings describe this simple native simulation, not externally coupled or more detailed equipment models.

`node viewer/design/annual-check.cjs` checks the served prototype at port 8715 and Optuna Dashboard at port 8090.
With those services running and generated recordings imported using `viewer/design/import_infrastructure.py`, Chrome measured approximately 174 ms to the eight-run table and 217 ms to three loaded trajectory overlays.
No CSV was fetched during summary browsing.
All 8,760 points per annual signal were retained; a one-week zoom remained linked across grid power and battery state.
Missing battery signals were explicitly identified for setups without storage.
Desktop (1440 px) and phone (390 px) screenshots, plus timing JSON, are under `results/viewer-proposal/screenshots-annual/`.
Both the Vessim prototype and the annual Optuna Pareto view were opened in Chrome without page errors.

The prototype retains signals up to 10,000 points in full; larger signals use its bounded extrema-preserving overview.
This differs from the production viewer's 4,000-point reduction described above.
The original CSV remains downloadable.
Neither implementation currently fetches finer samples on zoom for larger signals.

The prototype's `node viewer/design/order-check.cjs` additionally verifies that selection order drives trajectory series, legends, and selected CSV export.
Dragging run names reorders selections.
Keyboard arrow keys also reorder focused names.
Colors and zoom survive reordering, and table sorting and study switching preserve each study's selection order.
The check also exercises removal/reselection, empty selections, and desktop/mobile layouts.
Signal charts follow the Signals menu order, grouped by microgrid and category.
The same browser check verifies menu/chart order agreement, selection-order independence, hide/restore position retention, and editable run color swatches.
Colors apply across signal charts, and changing visible signals preserves the shared zoom.
The Signals picker groups by site and recorded field namespace.
A two-site browser fixture checks independent selection of matching field names, retained collapsed sites, and desktop/mobile rendering; a model check covers custom field fallback.

`node viewer/design/results-check.cjs` checks the simplified single-run configuration view, conditional controls for repeated runs, collapsed descriptions, column dragging and sorting, automatic units, overrides, consistent scatter/export values, per-study preferences, lazy CSV loading, and desktop/mobile layouts.
Energy totals such as 8.9 billion Wh display as 8.9 GWh; filters do not change the scale.
Eleven DOM-free model/unit tests cover completed-only catalogs, metric compatibility, conversion factors, missing/zero values, and unknown units.
The prototype uses a small explicit conversion list (energy, power, CO2e mass), not a general unit parser.
The prototype now has Results and Time series as its main views.
Compare and baseline differences were removed; old Compare links return to Results.
Full configuration and execution details remain available by opening a run.
Configuration ranges and explicit summary statistics remain in Results; the former Compare distribution plots have been removed with that page.
Draft study indexes now omit copied parameter values, conditions, and run IDs.
Run files supply the recorded evidence; optional configuration names fall back to configuration IDs.
An optional `run_parameters` list identifies top-level realization inputs without copying their values.
Shared input values are derived only within the explicit groups, never used to infer membership.
Model checks cover absent names, duplicate run identities, varying inputs, and legacy indexes whose copied parameter values disagree with the recorded evidence.

Four scenario tests check reproducible annual inputs, resolution consistency, grid-only energy/emissions integrals, storage balance including the final held interval, CSV/summary agreement, objective validity, output preservation, and Optuna trial links/evaluation-setting guards.
The combined scenario, experiment-file, and recorder/result suite passed 65 tests.
Frontend lint/build and the retained-cache upgrade regression also passed.
All inputs and equipment-emissions coefficients are synthetic; the scenario is workflow evidence, not a validated sizing recommendation.

### General limits

The viewer opens a recorded catalog snapshot.
It does not launch scenarios, resume optimization, serve live monitoring, or interpret arbitrary metric units.
Numeric custom trajectory fields without known units are inspectable individually but do not appear in overlays.
Baseline deltas require matching known units.
Differences in metric descriptions and assumptions are displayed beside values; the viewer does not infer scientific comparability or whether a change is beneficial.
There is no automatic migration of legacy metadata.yaml recordings.
