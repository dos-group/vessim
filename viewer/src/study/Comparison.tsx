import { useMemo, useState } from 'react'
import type { Column, Run } from './model'
import {
  columnLabel,
  delta,
  flatten,
  format,
  metricDifferences,
  stable,
} from './model'
import { Status } from './Explorer'
import { Overlays } from './Trajectories'

export function Comparison({
  runs,
  columns,
  inspect,
}: {
  runs: Run[]
  columns: Column[]
  inspect: (key: string) => void
}) {
  const [baselineKey, setBaseline] = useState('')
  const [charts, setCharts] = useState(false)
  const baseline = runs.find((r) => r.key === baselineKey) ?? runs[0]
  const metrics = columns.filter(
    (c) => c.kind === 'metric' && runs.some((r) => c.id in r.values),
  )
  const configs = useMemo(
    () =>
      runs.map((r) =>
        flatten({
          parameters: r.record.parameters,
          config: r.record.config,
          recording: {
            simulated_duration_s: r.record.execution.simulated_duration ?? null,
            steps: r.record.execution.steps ?? null,
            status: r.record.execution.status,
          },
        }),
      ),
    [runs],
  )
  const differences = [
    ...new Set(configs.flatMap((c) => Object.keys(c))),
  ].filter((key) => new Set(configs.map((c) => stable(c[key]))).size > 1)
  if (runs.length < 2)
    return (
      <div className="empty">
        <h2>Choose your comparison.</h2>
        <p>
          Select two or more runs in Explore to compare their outcomes and
          configuration.
        </p>
      </div>
    )
  if (runs.length > 8)
    return (
      <div className="empty">
        <h2>Narrow your comparison to eight runs.</h2>
        <p>
          {runs.length} runs are selected. Filter and export large selections in
          Explore; choose up to eight for a detailed comparison.
        </p>
      </div>
    )
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">SIDE BY SIDE</p>
          <h1>Understand the difference.</h1>
          <p className="subtitle">
            Recorded outcomes, with the assumptions behind them.
          </p>
        </div>
        <label>
          Baseline
          <select
            aria-label="Baseline"
            value={baseline.key}
            onChange={(e) => setBaseline(e.target.value)}
          >
            {runs.map((r) => (
              <option key={r.key} value={r.key}>
                {r.record.run_id}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="comparison-cards">
        {runs.map((r) => (
          <button
            key={r.key}
            className={`comparison-card ${r.key === baseline.key ? 'baseline-card' : ''}`}
            onClick={() => inspect(r.key)}
          >
            <span className="eyebrow">
              {r.key === baseline.key ? 'BASELINE' : 'COMPARISON RUN'}{' '}
              <span>↗</span>
            </span>
            <h3>{r.record.run_id}</h3>
            <Status value={r.record.execution.status} />
          </button>
        ))}
      </div>
      {runs.some((r) => r.record.execution.status !== 'completed') && (
        <div className="notice">
          This comparison includes unfinished or unsuccessful runs. Their
          recorded values may describe only part of the requested horizon.
        </div>
      )}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">RECORDED RESULTS</p>
            <h2>Metric comparison</h2>
          </div>
          <span className="subtle">Δ against {baseline.record.run_id}</span>
        </div>
        <p className="section-note">
          Deltas require matching known units. Descriptions and assumptions that
          differ are marked beside each value. Review the horizons and scenario
          conditions below when interpreting a comparison.
        </p>
        <div className="table-scroll">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Metric / scope</th>
                {runs.map((r) => (
                  <th key={r.key}>{r.record.run_id}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((c) => (
                <tr key={c.id}>
                  <th title={columnLabel(c)}>
                    <small>
                      {c.scope} · {c.unit}
                    </small>
                    {c.label}
                  </th>
                  {runs.map((r) => {
                    const d = delta(r, baseline, c)
                    return (
                      <td key={r.key}>
                        <strong>{format(r.values[c.id], c.unit)}</strong>
                        {r !== baseline && (
                          <small className="delta">
                            {d
                              ? `${d.absolute >= 0 ? '+' : ''}${format(d.absolute, c.unit)}${d.percent !== null ? ` (${d.percent >= 0 ? '+' : ''}${d.percent.toFixed(1)}%)` : ' · baseline zero'}`
                              : r.values[c.id] != null &&
                                  baseline.values[c.id] != null
                                ? 'Unknown or incompatible units · no delta'
                                : 'Unavailable · no delta'}
                          </small>
                        )}
                        {r !== baseline &&
                          metricDifferences(r, baseline, c).map(
                            (difference) => (
                              <small className="subtle" key={difference}>
                                {difference}
                              </small>
                            ),
                          )}
                        <details className="metric-definition">
                          <summary>Definition</summary>
                          <p>
                            {r.definitions[c.id]?.description ||
                              'No description recorded.'}
                          </p>
                          <pre>
                            {JSON.stringify(
                              r.definitions[c.id]?.assumptions ?? {},
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!metrics.length && (
          <p className="empty">No summary metrics recorded.</p>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">WHAT CHANGED</p>
            <h2>Parameters & configuration</h2>
          </div>
          <span className="pill">{differences.length} differing fields</span>
        </div>
        <div className="table-scroll">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Field</th>
                {runs.map((r) => (
                  <th key={r.key}>{r.record.run_id}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {differences.map((key) => (
                <tr key={key}>
                  <th>{(JSON.parse(key) as string[]).join(' / ')}</th>
                  {configs.map((c, i) => (
                    <td key={runs[i].key}>{format(c[key])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!differences.length && (
          <p className="empty">
            These runs have identical recorded parameters and configuration.
          </p>
        )}
      </section>
      {charts ? (
        <Overlays key={runs.map((r) => r.key).join(',')} runs={runs} />
      ) : (
        <section className="panel overlay-invitation">
          <div>
            <p className="eyebrow">GO BEYOND THE SUMMARY</p>
            <h2>Compare behavior over time</h2>
            <p>
              Load recordings only when you need them. Align by elapsed time or
              recorded UTC time.
            </p>
          </div>
          <button className="button primary" onClick={() => setCharts(true)}>
            Load trajectory comparison →
          </button>
        </section>
      )}
    </>
  )
}
