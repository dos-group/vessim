import { useEffect, useId, useMemo, useState } from 'react'
import type { Run } from './model'
import { human } from './model'
import type { Trajectory } from './trajectory'
import { fieldLabel, timestamp } from './trajectory'
import { Chart } from './Chart'
import { colors } from './colors'

function useRecording(run: Run) {
  const [state, setState] = useState<{ data?: Trajectory; error?: string }>({})
  useEffect(() => {
    if (!run.trajectory) return
    const worker = new Worker(
      new URL('./trajectory.worker.ts', import.meta.url),
      { type: 'module' },
    )
    worker.onmessage = (event) => {
      setState(event.data)
      worker.terminate()
    }
    worker.onerror = () => {
      setState({ error: 'Could not parse this recording.' })
      worker.terminate()
    }
    worker.postMessage({
      url: new URL(run.trajectory.url, document.baseURI).href,
    })
    return () => worker.terminate()
  }, [run])
  return state
}
export function RunCharts({ run }: { run: Run }) {
  const state = useRecording(run)
  const [grid, setGrid] = useState('')
  const [extra, setExtra] = useState('')
  const [alignment, setAlignment] = useState('elapsed')
  const group = useId()
  if (!run.trajectory)
    return (
      <div className="empty">
        <span className="empty-icon">↗</span>
        <h3>A compact result, ready to compare</h3>
        <p>
          This run contains summary metrics only. Enable time-series recording
          in Python when you need to investigate its behavior.
        </p>
      </div>
    )
  if (state.error) return <div className="notice error">{state.error}</div>
  if (!state.data)
    return (
      <div className="empty" role="status">
        Loading recording in the background…
      </div>
    )
  const grids = [...new Set(state.data.series.map((s) => s.grid))]
  const active = grid || grids[0]
  const series = state.data.series.filter((s) => s.grid === active)
  const origin = timestamp(run.record.config.environment?.sim_start)
  const elapsed = alignment === 'elapsed'
  const groups = [
    {
      title: 'Power balance',
      fields: series.filter(
        (s) => s.field === 'p_grid' || s.field === 'p_delta',
      ),
      unit: 'W',
    },
    {
      title: 'Actor power',
      fields: series.filter(
        (s) => s.field.startsWith('actor_states.') && s.unit === 'W',
      ),
      unit: 'W',
    },
    {
      title: 'State of charge',
      fields: series.filter(
        (s) => s.field.startsWith('dispatch_states.') && s.unit === '1',
      ),
      unit: '1',
    },
  ]
  const primary = new Set(groups.flatMap((g) => g.fields.map((s) => s.id)))
  const others = series.filter((s) => !primary.has(s.id))
  const custom = others.find((s) => s.id === extra) ?? others[0]
  if (custom)
    groups.push({
      title: human(fieldLabel(custom.field)),
      fields: [custom],
      unit: custom.unit,
    })
  return (
    <>
      <div className="toolbar">
        <label>
          Microgrid
          <select
            value={active ?? ''}
            onChange={(e) => setGrid(e.target.value)}
          >
            {grids.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </label>
        <label>
          Time axis
          <select
            value={alignment}
            onChange={(e) => setAlignment(e.target.value)}
          >
            <option value="elapsed">Elapsed from simulation start (h)</option>
            <option value="absolute">Recorded time (UTC)</option>
          </select>
        </label>
        <a
          className="button"
          href={run.trajectory.url}
          download={`${run.record.run_id}.csv`}
        >
          Download recording ↓
        </a>
      </div>
      <p className="subtle">
        {state.data.rows.toLocaleString()} observations · linked zoom and cursor
        · naive timestamps interpreted as UTC
      </p>
      {state.data.warnings.map((w) => (
        <div className="notice" key={w}>
          {w}
        </div>
      ))}
      {elapsed && !Number.isFinite(origin) ? (
        <div className="notice error">
          Simulation start is unavailable. Select recorded time to inspect this
          trajectory.
        </div>
      ) : (
        groups
          .filter((g) => g.fields.length)
          .map((g) => (
            <section className="chart-panel" key={g.title}>
              <div className="panel-heading">
                <h3>{g.title}</h3>
                <span className="subtle">
                  {g.unit === 'unknown'
                    ? 'Unit not recorded'
                    : g.unit === '1'
                      ? 'Fraction'
                      : g.unit}
                </span>
              </div>
              {g.fields[0] === custom && (
                <label className="signal-picker">
                  Signal
                  <select
                    value={custom.id}
                    onChange={(e) => setExtra(e.target.value)}
                  >
                    {others.map((s) => (
                      <option value={s.id} key={s.id}>
                        {human(fieldLabel(s.field))}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <Chart
                group={group}
                height={260}
                option={{
                  legend: {
                    type: 'scroll',
                    bottom: 0,
                    textStyle: { color: 'inherit' },
                  },
                  xAxis: {
                    type: elapsed ? 'value' : 'time',
                    name: elapsed ? 'h' : 'UTC',
                    axisLabel: { hideOverlap: true },
                  },
                  useUTC: true,
                  dataZoom: [{ type: 'inside', filterMode: 'none' }],
                  series: g.fields.map((s) => ({
                    name: human(fieldLabel(s.field)),
                    type: 'line',
                    showSymbol: false,
                    connectNulls: false,
                    step: 'end',
                    data: s.points.map(([t, v]) => [
                      elapsed ? (t - origin) / 3600000 : t,
                      v,
                    ]),
                  })),
                }}
              />
            </section>
          ))
      )}
      {!series.length && (
        <div className="empty">No numeric signals were recorded.</div>
      )}
    </>
  )
}
function OverlayLoader({
  run,
  ready,
}: {
  run: Run
  ready: (key: string, state: { data?: Trajectory; error?: string }) => void
}) {
  const state = useRecording(run)
  useEffect(() => {
    if (state.data || state.error) ready(run.key, state)
  }, [run.key, state, ready])
  return null
}
export function Overlays({ runs }: { runs: Run[] }) {
  const [loaded, setLoaded] = useState<
    Record<string, { data?: Trajectory; error?: string }>
  >({})
  const [signal, setSignal] = useState('')
  const [alignment, setAlignment] = useState('elapsed')
  const ready = useMemo(
    () => (key: string, state: { data?: Trajectory; error?: string }) =>
      setLoaded((prev) => ({ ...prev, [key]: state })),
    [],
  )
  const available = runs.filter((r) => r.trajectory)
  const candidates =
    loaded[available[0]?.key]?.data?.series.filter(
      (s) => s.unit !== 'unknown',
    ) ?? []
  const common = candidates.filter((s) =>
    available.every((r) =>
      loaded[r.key]?.data?.series.some(
        (other) => other.id === s.id && other.unit === s.unit,
      ),
    ),
  )
  const active = common.find((s) => s.id === signal) ?? common[0]
  const elapsed = alignment === 'elapsed'
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">BEHAVIOR OVER TIME</p>
          <h2>Trajectory comparison</h2>
        </div>
      </div>
      {available.map((r) => (
        <OverlayLoader key={r.key} run={r} ready={ready} />
      ))}
      {runs
        .filter((r) => !r.trajectory)
        .map((r) => (
          <p className="notice" key={r.key}>
            {r.record.run_id}: summary only; excluded from overlays.
          </p>
        ))}
      {available.map(
        (r) =>
          loaded[r.key]?.error && (
            <p className="notice error" key={r.key}>
              {r.record.run_id}: {loaded[r.key].error}
            </p>
          ),
      )}
      {available.length < 2 ? (
        <p className="empty">
          Select at least two runs with recorded trajectories.
        </p>
      ) : available.some((r) => !loaded[r.key]) ? (
        <p className="empty" role="status">
          Loading selected recordings…
        </p>
      ) : !active ? (
        <p className="empty">
          No compatible signals across these recordings. Overlays require
          matching microgrid, field, and a known unit. Inspect runs individually
          for custom signals.
        </p>
      ) : (
        <>
          <div className="toolbar">
            <label>
              Shared signal
              <select
                value={active.id}
                onChange={(e) => setSignal(e.target.value)}
              >
                {common.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.grid} · {human(fieldLabel(s.field))} ({s.unit})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Align by
              <select
                value={alignment}
                onChange={(e) => setAlignment(e.target.value)}
              >
                <option value="elapsed">
                  Elapsed from simulation start (h)
                </option>
                <option value="absolute">Recorded time (UTC)</option>
              </select>
            </label>
          </div>
          <p className="subtle">
            Only recorded observations are drawn. Runs are not interpolated onto
            a shared sampling grid. Overview sampling may preserve peaks with
            fewer points.
          </p>
          {elapsed &&
          available.some(
            (r) =>
              !Number.isFinite(
                timestamp(r.record.config.environment?.sim_start),
              ),
          ) ? (
            <p className="notice error">
              A simulation start is missing. Choose recorded time.
            </p>
          ) : (
            <Chart
              option={{
                useUTC: true,
                legend: { bottom: 0, type: 'scroll' },
                xAxis: {
                  type: elapsed ? 'value' : 'time',
                  name: elapsed ? 'h' : 'UTC',
                },
                dataZoom: [{ type: 'inside', filterMode: 'none' }],
                series: available.map((r, i) => ({
                  name: r.record.run_id,
                  type: 'line',
                  showSymbol: false,
                  step: 'end',
                  connectNulls: false,
                  color: colors[i % colors.length],
                  data: loaded[r.key]
                    .data!.series.find((s) => s.id === active.id)!
                    .points.map(([t, v]) => [
                      elapsed
                        ? (t -
                            timestamp(r.record.config.environment?.sim_start)) /
                          3600000
                        : t,
                      v,
                    ]),
                })),
              }}
            />
          )}
        </>
      )}
    </section>
  )
}
