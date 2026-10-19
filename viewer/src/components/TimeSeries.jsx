import { useEffect, useMemo, useSyncExternalStore } from 'react'
import { useViewer } from '../context.jsx'
import { signalGroups, visibleSignals, human } from '../model.js'
import { signalLabel } from '../presentation.js'
import { inSelectionOrder, toggle } from '../state.js'
import { unitOptions } from '../units.js'
import { prepareTrajectory, trajectoryOptions } from '../trajectory.js'
import {
  Checkbox,
  ChoiceGroup,
  Heading,
  NavLink,
  Picker,
  Select,
  UnitSelect,
} from './controls.jsx'
import { SelectionOrder } from './Ordering.jsx'
import { Representation } from './Representation.jsx'
import { Chart } from './Chart.jsx'

function TrajectoryChart({ signal, runs, chosen }) {
  const { study, view: s, patch, recordings } = useViewer()
  const {
    alignment,
    timeMode,
    timeConfigs,
    timeStat,
    timeSpread,
    timeIndividuals,
    runColors,
    configColors,
  } = s
  const preference = s.signalUnits[signal.id]
  const prepared = useMemo(
    () =>
      prepareTrajectory(
        study,
        {
          alignment,
          timeMode,
          timeConfigs,
          timeStat,
          timeSpread,
          timeIndividuals,
          runColors,
          configColors,
        },
        signal,
        runs.map((run) => ({
          run,
          signal: recordings
            .get(run)
            .series.find(
              (sig) => sig.id === signal.id && sig.unit === signal.unit,
            ),
        })),
        preference,
      ),
    [
      study,
      alignment,
      timeMode,
      timeConfigs,
      timeStat,
      timeSpread,
      timeIndividuals,
      runColors,
      configColors,
      signal,
      runs,
      recordings,
      preference,
    ],
  )
  const { missing, magnitude, spec, error } = prepared
  const option = useMemo(
    () =>
      trajectoryOptions(
        prepared.series,
        alignment,
        s.zoom,
        prepared.spec,
        prepared.magnitude,
      ),
    [prepared, alignment, s.zoom],
  )
  return (
    <section className="panel trajectory-panel" data-signal-panel={signal.id}>
      <div className="chart-heading">
        <h2>{signalLabel(signal)}</h2>
        <span>
          {study.singleMicrogrid ? '' : signal.grid}
          {unitOptions(signal.unit).length < 2
            ? `${study.singleMicrogrid ? '' : ' · '}${spec.unit === '1' ? 'fraction' : spec.unit}`
            : ''}
        </span>
        <UnitSelect
          label={`Display unit for ${signalLabel(signal)}`}
          unit={signal.unit}
          magnitude={magnitude}
          value={s.signalUnits[signal.id]}
          onChange={(unit) =>
            patch((v) => ({
              signalUnits: { ...v.signalUnits, [signal.id]: unit },
            }))
          }
        />
        <button
          className="remove-signal"
          aria-label={`Remove ${signalLabel(signal)} chart`}
          onClick={() =>
            patch({ signals: chosen.filter((id) => id !== signal.id) })
          }
        >
          ×
        </button>
      </div>
      {missing.length > 0 && (
        <p className="note">Signal missing in: {missing.join(', ')}</p>
      )}
      {prepared.notes.length > 0 && (
        <p className="note">{prepared.notes.join(' · ')}</p>
      )}
      {error ? (
        <p className="notice">{error}</p>
      ) : (
        <Chart
          className="time-chart"
          label={`${signal.field} trajectory chart`}
          option={option}
          group="vessim-time"
          onZoom={(zooms) => patch({ zoom: zooms[0] })}
        />
      )}
    </section>
  )
}
function SignalsPicker({ groups, chosen }) {
  const { study, patch } = useViewer()
  const single = study.singleMicrogrid && groups.length === 1
  const contents = (site) =>
    site.groups.map((group) => (
      <ChoiceGroup key={group.label} label={group.label}>
        {group.signals.map((sig) => (
          <Checkbox
            key={sig.id}
            data-signal={sig.id}
            label={`${signalLabel(sig)} (${sig.unit})`}
            aria-label={`${single ? '' : `${sig.grid} · `}${signalLabel(sig)} (${sig.unit})`}
            checked={chosen.includes(sig.id)}
            onChange={(enabled) =>
              patch({
                signals: enabled
                  ? [...chosen, sig.id]
                  : chosen.filter((id) => id !== sig.id),
              })
            }
          />
        ))}
      </ChoiceGroup>
    ))
  return (
    <Picker label={`Signals (${chosen.length})`}>
      {groups.map((site) =>
        single ? (
          <div key={site.site}>{contents(site)}</div>
        ) : (
          <details className="signal-site" key={site.site} open>
            <summary>Microgrid · {site.site}</summary>
            {contents(site)}
          </details>
        ),
      )}
    </Picker>
  )
}
export function TimeSeries() {
  const { study, view: s, patch, recordings } = useViewer()
  const recorded = useSyncExternalStore(
    recordings.subscribe,
    recordings.snapshot,
  )
  const aggregate = !study.singleRun && s.timeMode === 'configurations'
  const entries = useMemo(
    () =>
      inSelectionOrder(
        aggregate ? study.configurations : study.runs,
        aggregate ? s.timeConfigs : s.runs,
      ),
    [study, aggregate, s.timeConfigs, s.runs],
  )
  const runs = useMemo(
    () => (aggregate ? entries.flatMap((c) => c.runs) : entries),
    [aggregate, entries],
  )
  const pool = aggregate
    ? study.configurations
    : s.configs.size
      ? study.runs.filter((r) => s.configs.has(r.configuration.key))
      : study.runs
  const kind = aggregate ? 'timeConfigs' : 'runs',
    label = aggregate ? 'configurations' : 'runs'
  const overLimit =
    runs.length > (aggregate ? 100 : study.singleRun ? 8 : 50) ||
    (aggregate && entries.length > 8)
  useEffect(() => {
    if (!overLimit) runs.forEach((run) => recordings.ensure(run))
  }, [runs, recordings, overLimit])
  const pending = runs.some(
    (run) =>
      run.trajectoryUrl &&
      (!recordings.get(run) || recordings.get(run).pending),
  )
  const loaded = useMemo(
    () => runs.filter((run) => recorded.get(run.trajectoryUrl)?.series),
    [runs, recorded],
  )
  const available = useMemo(() => {
    const signals = new Map()
    loaded.forEach((run) =>
      recordings
        .get(run)
        .series.forEach((signal) => signals.set(signal.id, signal)),
    )
    return visibleSignals(
      [...signals.values()],
      loaded.map((run) => ({
        config: run.record.config,
        series: recordings.get(run).series,
      })),
    ).sort(
      (a, b) =>
        a.grid.localeCompare(b.grid, undefined, { numeric: true }) ||
        Number(b.gridPower) - Number(a.gridPower) ||
        signalLabel(a).localeCompare(signalLabel(b), undefined, {
          numeric: true,
        }) ||
        a.id.localeCompare(b.id),
    )
  }, [loaded, recordings])
  const groups = signalGroups(available)
  const validSignals = s.signals?.filter((id) =>
    available.some((sig) => sig.id === id),
  )
  const selectedSignals =
    (s.signals?.length && !validSignals.length ? null : validSignals) ??
    available
      .filter(
        (sig) =>
          sig.gridPower ||
          (study.singleMicrogrid && sig.field.endsWith('.soc')),
      )
      .slice(0, 3)
      .map((sig) => sig.id)
  const chosen = groups
    .flatMap((site) => site.groups.flatMap((group) => group.signals))
    .filter((sig) => selectedSignals.includes(sig.id))
  const notices = runs.flatMap((run) =>
    !run.trajectoryUrl
      ? [`${run.key}: no trajectory was recorded.`]
      : recordings.get(run)?.error
        ? [`${run.key}: ${recordings.get(run).error}`]
        : [],
  )
  return (
    <>
      <Heading
        title="Time series"
        actions={
          <NavLink className="button" href="#results">
            Back to results
          </NavLink>
        }
      >
        {study.name} · {entries.length} selected{' '}
        {entries.length === 1 ? label.slice(0, -1) : label}
      </Heading>
      <Representation trajectory />
      <div className="toolbar">
        <Picker label={`Choose ${label} (${entries.length})`}>
          {pool.map((entry) => (
            <Checkbox
              key={entry.key}
              label={`${aggregate ? entry.name : entry.key}${aggregate ? ` · ${entry.runs.length} runs` : !entry.trajectoryUrl ? ' · no recording' : ''}`}
              data-time-config={aggregate ? entry.key : undefined}
              data-time-run={!aggregate ? entry.key : undefined}
              checked={s[kind].has(entry.key)}
              onChange={(enabled) =>
                patch((v) => ({ [kind]: toggle(v[kind], entry.key, enabled) }))
              }
            />
          ))}
        </Picker>
        <Select
          id="alignment"
          label="Time alignment"
          value={s.alignment}
          onChange={(alignment) => patch({ alignment })}
          options={[
            { value: 'elapsed', label: 'Elapsed from simulation start (h)' },
            { value: 'absolute', label: 'Recorded time (UTC)' },
          ]}
        />
        <button onClick={() => patch({ zoom: { start: 0, end: 100 } })}>
          Reset zoom
        </button>
        <button
          disabled={!entries.length}
          onClick={() => patch({ [kind]: new Set() })}
        >
          Clear {label}
        </button>
      </div>
      <SelectionOrder entries={entries} kind={kind} />
      {!aggregate && !study.singleRun && runs.length > 8 && (
        <div className="configuration-legend">
          {[...new Set(runs.map((r) => r.configuration))].map((c) => (
            <label key={c.key}>
              <input
                type="color"
                className="run-color"
                value={s.configColors[c.key]}
                aria-label={`Color for ${c.name}`}
                onChange={(e) =>
                  patch((v) => ({
                    configColors: {
                      ...v.configColors,
                      [c.key]: e.target.value,
                    },
                  }))
                }
              />
              {c.name}
            </label>
          ))}
        </div>
      )}
      {!runs.length ? (
        <p className="empty">Choose {label} to plot recorded trajectories.</p>
      ) : overLimit ? (
        <p className="empty">
          Choose{' '}
          {aggregate
            ? 'up to eight configurations and 100 recorded runs'
            : study.singleRun
              ? 'up to eight runs'
              : 'up to 50 runs'}{' '}
          for readable overlays.
        </p>
      ) : (
        <>
          {aggregate && (
            <p className="note">
              {human(s.timeStat)} at each matching timestamp
              {s.timeSpread === 'none'
                ? ''
                : s.timeSpread === 'iqr'
                  ? ' with the middle 50% of recorded values'
                  : ' with the observed min–max range'}
              . Summaries use all available runs in each selected configuration.
              Bands are not confidence intervals.
            </p>
          )}
          {notices.map((notice) => (
            <p className="notice" key={notice}>
              {notice}
            </p>
          ))}
          {pending ? (
            <p role="status">Loading selected recordings…</p>
          ) : (
            loaded.length > 0 && (
              <>
                <div className="toolbar">
                  <SignalsPicker
                    groups={groups}
                    chosen={chosen.map((sig) => sig.id)}
                  />
                  <Picker label="Download CSV">
                    {loaded.map((run) => (
                      <a key={run.key} href={run.trajectoryUrl} download>
                        {run.key}
                      </a>
                    ))}
                  </Picker>
                </div>
                {loaded.map((run) => (
                  <div key={run.key}>
                    {recordings.get(run).malformed > 0 && (
                      <p className="notice">
                        {run.key}: {recordings.get(run).malformed} malformed
                        rows skipped.
                      </p>
                    )}
                    {recordings
                      .get(run)
                      .series.some((sig) => sig.count > sig.points.length) && (
                      <p className="note">
                        Large signals use an extrema-preserving overview.
                        Download CSV for full resolution.
                      </p>
                    )}
                  </div>
                ))}
                {!chosen.length && (
                  <p className="empty">Choose signals to plot.</p>
                )}
                {chosen.map((signal) => (
                  <TrajectoryChart
                    key={signal.id}
                    signal={signal}
                    runs={loaded}
                    chosen={chosen.map((sig) => sig.id)}
                  />
                ))}
              </>
            )
          )}
        </>
      )}
    </>
  )
}
