import { useState } from 'react'
import type { Column, Run } from './model'
import { download, format } from './model'
import { Status } from './Explorer'
import { RunCharts } from './Trajectories'

export function Inspector({
  run,
  columns,
  back,
  selected,
  toggle,
}: {
  run: Run
  columns: Column[]
  back: () => void
  selected: boolean
  toggle: () => void
}) {
  const [tab, setTab] = useState('metrics')
  const [scope, setScope] = useState('all')
  const metrics = columns.filter(
    (c) => c.kind === 'metric' && c.id in run.values,
  )
  const scopes = [...new Set(metrics.map((c) => c.scope))]
  return (
    <>
      <button className="text-button back-link" onClick={back}>
        ← Back to study
      </button>
      <div className="page-title">
        <div>
          <p className="eyebrow">EXPERIMENT DETAIL</p>
          <h1 className="run-title">{run.record.run_id}</h1>
          <div className="run-meta">
            <Status value={run.record.execution.status} />
            <span>{run.source}</span>
            <span>
              {run.trajectory ? 'Trajectory recorded' : 'Summary only'}
            </span>
          </div>
        </div>
        <button
          className={`button ${selected ? '' : 'primary'}`}
          onClick={toggle}
        >
          {selected ? '✓ Selected for comparison' : '+ Select for comparison'}
        </button>
      </div>
      <div className="stats">
        <div>
          <span>Simulated duration</span>
          <strong>
            {format(
              run.record.execution.simulated_duration == null
                ? null
                : run.record.execution.simulated_duration / 3600,
            )}{' '}
            <small>h</small>
          </strong>
        </div>
        <div>
          <span>Execution time</span>
          <strong>
            {format(run.record.execution.wall_time)} <small>s</small>
          </strong>
        </div>
        <div>
          <span>Microgrids</span>
          <strong>{Object.keys(run.record.config.microgrids).length}</strong>
        </div>
        <div>
          <span>Summary metrics</span>
          <strong>{metrics.length}</strong>
        </div>
      </div>
      {run.record.execution.status !== 'completed' && (
        <div className="notice">
          This run is {run.record.execution.status}. Metrics may be partial;
          unavailable values are not treated as zero.{' '}
          {String(run.record.execution.metric_error ?? '')}
        </div>
      )}
      <div
        className="tabs inspector-tabs"
        role="tablist"
        aria-label="Run detail"
      >
        {[
          ['metrics', 'Metrics'],
          ['trajectory', 'Time series'],
          ['configuration', 'Configuration'],
        ].map(([value, label]) => (
          <button
            role="tab"
            aria-selected={tab === value}
            key={value}
            className={tab === value ? 'active' : ''}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'metrics' && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">AUTHORITATIVE RECORDED VALUES</p>
              <h2>Outcomes & assumptions</h2>
            </div>
            <label>
              Scope
              <select
                aria-label="Metric scope"
                value={scope}
                onChange={(e) => setScope(e.target.value)}
              >
                <option value="all">All scopes</option>
                {scopes.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="metric-grid">
            {metrics
              .filter((c) => scope === 'all' || c.scope === scope)
              .map((c) => (
                <article className="metric-card" key={c.id}>
                  <p className="eyebrow">{c.scope}</p>
                  <h3>{c.label}</h3>
                  <div className="metric-value">
                    {format(run.values[c.id])}
                    <span>{c.unit === '1' ? '' : c.unit}</span>
                  </div>
                  <p>
                    {run.definitions[c.id]?.description ||
                      'No description recorded.'}
                  </p>
                  {Object.keys(run.definitions[c.id]?.assumptions ?? {})
                    .length > 0 && (
                    <details>
                      <summary>Calculation assumptions</summary>
                      <pre>
                        {JSON.stringify(
                          run.definitions[c.id].assumptions,
                          null,
                          2,
                        )}
                      </pre>
                    </details>
                  )}
                </article>
              ))}
          </div>
          {!metrics.length && (
            <div className="empty">No summary metrics were recorded.</div>
          )}
        </section>
      )}
      {tab === 'trajectory' && (
        <section className="panel">
          <RunCharts run={run} />
        </section>
      )}
      {tab === 'configuration' && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">REPRODUCIBILITY</p>
              <h2>The recorded setup</h2>
            </div>
            <button
              className="button"
              onClick={() =>
                download(
                  `${run.record.run_id}-summary.json`,
                  JSON.stringify({ ...run.record, timeseries: null }, null, 2),
                  'application/json',
                )
              }
            >
              Export summary metadata ↓
            </button>
          </div>
          <p className="section-note">
            Descriptive metadata from Python, not a serialized executable model.
            This export omits the trajectory.
          </p>
          {[
            ['Parameters', run.record.parameters],
            ['Configuration', run.record.config],
            ['Execution', run.record.execution],
          ].map(([label, value]) => (
            <div className="config-section" key={String(label)}>
              <h3>{String(label)}</h3>
              <pre>{JSON.stringify(value, null, 2)}</pre>
            </div>
          ))}
        </section>
      )}
    </>
  )
}
