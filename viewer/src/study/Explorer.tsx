import { useDeferredValue, useMemo, useState } from 'react'
import type { Catalog, Column } from './model'
import { columnLabel, csv, download, format, numeric } from './model'
import { Chart } from './Chart'
import { useTheme } from '../theme'

export function Status({ value }: { value: string }) {
  return (
    <span className={`status status-${value}`}>
      <span />
      {value}
    </span>
  )
}
export function Explorer({
  catalog,
  selected,
  toggle,
  inspect,
  compare,
  selectMany,
  active,
}: {
  active: boolean
  catalog: Catalog
  selected: Set<string>
  toggle: (key: string) => void
  inspect: (key: string) => void
  compare: () => void
  selectMany: (keys: string[]) => void
}) {
  const { isDark } = useTheme()
  const { runs, columns } = catalog
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query.toLowerCase())
  const [status, setStatus] = useState('all')
  const [filterColumn, setFilterColumn] = useState('')
  const [min, setMin] = useState(''),
    [max, setMax] = useState('')
  const variableMetrics = useMemo(
    () =>
      columns.filter(
        (c) =>
          c.kind === 'metric' &&
          new Set(runs.map((r) => r.values[c.id])).size > 1,
      ),
    [columns, runs],
  )
  const [visible, setVisible] = useState<string[]>(() =>
    [
      ...columns.filter((c) => c.kind === 'parameter').slice(0, 3),
      ...variableMetrics.filter((c) => c.scope === 'Run').slice(0, 1),
      ...variableMetrics.filter((c) => c.scope !== 'Run').slice(0, 2),
    ].map((c) => c.id),
  )
  const [sort, setSort] = useState({ id: 'run', descending: false })
  const [page, setPage] = useState(0)
  const [xId, setX] = useState(''),
    [yId, setY] = useState('')
  const [focused, setFocused] = useState<string | null>(null)
  const numericColumns = useMemo(
    () => columns.filter((c) => c.numeric),
    [columns],
  )
  const x =
    numericColumns.find((c) => c.id === xId) ??
    numericColumns.find((c) => c.kind === 'parameter') ??
    numericColumns[0]
  const y =
    numericColumns.find((c) => c.id === yId) ??
    variableMetrics.find((c) => c.scope !== 'Run') ??
    numericColumns.find((c) => c.kind === 'metric') ??
    numericColumns[1]
  const filtered = useMemo(
    () =>
      runs.filter((r) => {
        if (deferredQuery && !r.search.includes(deferredQuery)) return false
        if (
          status === 'selected'
            ? !selected.has(r.key)
            : status !== 'all' && r.record.execution.status !== status
        )
          return false
        if (filterColumn && (min !== '' || max !== '')) {
          const value = r.values[filterColumn]
          if (
            !numeric(value) ||
            (min !== '' && value < Number(min)) ||
            (max !== '' && value > Number(max))
          )
            return false
        }
        return true
      }),
    [runs, deferredQuery, status, selected, filterColumn, min, max],
  )
  const sorted = useMemo(
    () =>
      [...filtered].sort((a, b) => {
        const av = sort.id === 'run' ? a.record.run_id : a.values[sort.id]
        const bv = sort.id === 'run' ? b.record.run_id : b.values[sort.id]
        if (av == null) return bv == null ? 0 : 1
        if (bv == null) return -1
        const cmp =
          numeric(av) && numeric(bv)
            ? av - bv
            : String(av).localeCompare(String(bv), undefined, { numeric: true })
        return sort.descending ? -cmp : cmp
      }),
    [filtered, sort],
  )
  const pages = Math.max(1, Math.ceil(sorted.length / 50)),
    currentPage = Math.min(page, pages - 1)
  const pageRuns = sorted.slice(currentPage * 50, (currentPage + 1) * 50)
  const tableColumns = columns.filter((c) => visible.includes(c.id))
  const points = useMemo(
    () =>
      x && y
        ? filtered.filter(
            (r) => numeric(r.values[x.id]) && numeric(r.values[y.id]),
          )
        : [],
    [filtered, x, y],
  )
  const pointRuns = useMemo(() => {
    // Deterministic sampling bounds rendering. Selected points are always retained.
    const stride = Math.max(1, Math.ceil(points.length / 10000))
    return points.filter((r, i) => i % stride === 0 || selected.has(r.key))
  }, [points, selected])
  const focus = runs.find((r) => r.key === focused)
  const selectedRuns = runs.filter((r) => selected.has(r.key))
  const setOrder = (id: string) =>
    setSort((prev) => ({
      id,
      descending: prev.id === id ? !prev.descending : false,
    }))
  const option = (c: Column) => (
    <option key={c.id} value={c.id}>
      {columnLabel(c)}
    </option>
  )
  const axisLabel = (c: Column) =>
    `${c.label}${c.unit && c.unit !== '1' ? ` (${c.unit})` : ''}`
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">SIMULATION STUDIES</p>
          <h1>Explore the possibilities.</h1>
          <p className="subtitle">
            Compare outcomes. Find the runs worth a closer look.
          </p>
        </div>
        <div className="study-label">
          <span className="label-dot" />
          {catalog.name}
        </div>
      </div>
      <div className="stats">
        <div>
          <span>Recorded runs</span>
          <strong>{runs.length.toLocaleString()}</strong>
        </div>
        <div>
          <span>Completed</span>
          <strong>
            {runs
              .filter((r) => r.record.execution.status === 'completed')
              .length.toLocaleString()}
          </strong>
        </div>
        <div>
          <span>Parameters</span>
          <strong>
            {columns.filter((c) => c.kind === 'parameter').length}
          </strong>
        </div>
        <div>
          <span>Recorded metrics</span>
          <strong>{columns.filter((c) => c.kind === 'metric').length}</strong>
        </div>
      </div>
      <section className="panel space-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">OUTCOME LANDSCAPE</p>
            <h2>See how choices change results</h2>
          </div>
          <span className="pill">
            {points.length.toLocaleString()} plottable runs
          </span>
        </div>
        {x && y ? (
          <>
            <div className="axis-controls">
              <label>
                Horizontal axis
                <select
                  aria-label="Horizontal axis"
                  value={x.id}
                  onChange={(e) => setX(e.target.value)}
                >
                  {numericColumns.map(option)}
                </select>
              </label>
              <span className="axis-cross">×</span>
              <label>
                Vertical axis
                <select
                  aria-label="Vertical axis"
                  value={y.id}
                  onChange={(e) => setY(e.target.value)}
                >
                  {numericColumns.map(option)}
                </select>
              </label>
            </div>
            <div className="scatter-layout">
              <div className="scatter-chart">
                {active && (
                  <Chart
                    onPoint={(key) => {
                      setFocused(key)
                      if (!selected.has(key)) toggle(key)
                    }}
                    option={{
                      tooltip: {
                        trigger: 'item',
                        renderMode: 'richText',
                        confine: true,
                      },
                      xAxis: {
                        type: 'value',
                        name: axisLabel(x),
                        nameLocation: 'middle',
                        nameGap: 32,
                        scale: true,
                        splitLine: { show: false },
                      },
                      yAxis: {
                        type: 'value',
                        name: axisLabel(y),
                        nameGap: 14,
                        scale: true,
                        axisLabel: { hideOverlap: true },
                      },
                      series: [
                        {
                          type: 'scatter',
                          symbolSize: 7,
                          data: pointRuns.map((r) => ({
                            name: r.record.run_id,
                            runKey: r.key,
                            value: [
                              r.values[x.id] as number,
                              r.values[y.id] as number,
                            ],
                            symbolSize: selected.has(r.key) ? 12 : 7,
                            itemStyle: {
                              color: selected.has(r.key)
                                ? '#d08039'
                                : isDark
                                  ? '#67c8b1'
                                  : '#168875',
                              opacity: selected.has(r.key) ? 1 : 0.72,
                            },
                          })),
                        },
                      ],
                    }}
                  />
                )}
              </div>
              <aside className="plot-guide">
                {focus ? (
                  <>
                    <span className="eyebrow">SELECTED POINT</span>
                    <h3>{focus.record.run_id}</h3>
                    <Status value={focus.record.execution.status} />
                    <dl>
                      <dt>{columnLabel(x)}</dt>
                      <dd>{format(focus.values[x.id], x.unit)}</dd>
                      <dt>{columnLabel(y)}</dt>
                      <dd>{format(focus.values[y.id], y.unit)}</dd>
                    </dl>
                    <button
                      className="button primary"
                      onClick={() => inspect(focus.key)}
                    >
                      Inspect run ↗
                    </button>
                  </>
                ) : (
                  <>
                    <span className="plot-glyph">↗</span>
                    <h3>Find your next question.</h3>
                    <p>
                      Choose two fields to reveal relationships across your
                      study. Click a point to select its run.
                    </p>
                    <p className="legend-note">
                      <i />
                      All runs <i className="selected-dot" />
                      Selected
                    </p>
                  </>
                )}
              </aside>
            </div>
            <p className="chart-footnote">
              {filtered.length - points.length} runs omitted for missing or
              nonnumeric axis values.{' '}
              {pointRuns.length < points.length &&
                `Showing a deterministic sample of ${pointRuns.length.toLocaleString()} points.`}{' '}
              Color indicates selection, not performance.
            </p>
          </>
        ) : (
          <div className="empty">
            Record numeric parameters or summary metrics to explore
            relationships.
          </div>
        )}
      </section>
      <section className="panel results-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">EXPERIMENT LIBRARY</p>
            <h2>
              Runs{' '}
              <span className="count">{filtered.length.toLocaleString()}</span>
            </h2>
          </div>
          <div className="actions">
            <button
              className="button"
              disabled={!selectedRuns.length}
              onClick={() =>
                download(
                  `${catalog.name}-selected.csv`,
                  csv(selectedRuns, tableColumns),
                )
              }
            >
              Export selected ↓
            </button>
            <button
              className="button primary"
              disabled={selected.size < 2}
              onClick={compare}
            >
              Compare {selected.size > 0 ? `(${selected.size})` : ''} →
            </button>
          </div>
        </div>
        <div className="toolbar filters">
          <label className="search-field">
            <span className="sr-only">Search runs</span>
            <input
              aria-label="Search runs"
              placeholder="Search run IDs, parameters, sources…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setPage(0)
              }}
            />
          </label>
          <label>
            <span className="sr-only">Status</span>
            <select
              aria-label="Filter status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value)
                setPage(0)
              }}
            >
              <option value="all">All statuses</option>
              <option value="selected">Selected runs</option>
              {['completed', 'failed', 'interrupted', 'running'].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <details className="column-picker">
            <summary className="button">
              Columns <span>☷</span>
            </summary>
            <div className="column-popover">
              {columns.map((c) => (
                <label key={c.id}>
                  <input
                    type="checkbox"
                    checked={visible.includes(c.id)}
                    onChange={() =>
                      setVisible((prev) =>
                        prev.includes(c.id)
                          ? prev.filter((id) => id !== c.id)
                          : [...prev, c.id],
                      )
                    }
                  />
                  {columnLabel(c)}
                </label>
              ))}
            </div>
          </details>
        </div>
        <div className="toolbar numeric-filter">
          <label>
            Filter a field
            <select
              aria-label="Numeric filter field"
              value={filterColumn}
              onChange={(e) => {
                setFilterColumn(e.target.value)
                setPage(0)
              }}
            >
              <option value="">Any value</option>
              {numericColumns.map(option)}
            </select>
          </label>
          <label>
            Minimum
            <input
              aria-label="Minimum value"
              type="number"
              disabled={!filterColumn}
              placeholder="No minimum"
              value={min}
              onChange={(e) => {
                setMin(e.target.value)
                setPage(0)
              }}
            />
          </label>
          <label>
            Maximum
            <input
              aria-label="Maximum value"
              type="number"
              disabled={!filterColumn}
              placeholder="No maximum"
              value={max}
              onChange={(e) => {
                setMax(e.target.value)
                setPage(0)
              }}
            />
          </label>
          {(query || status !== 'all' || filterColumn) && (
            <button
              className="text-button"
              onClick={() => {
                setQuery('')
                setStatus('all')
                setFilterColumn('')
                setMin('')
                setMax('')
                setPage(0)
              }}
            >
              Reset filters
            </button>
          )}
        </div>
        {selected.size > 0 && (
          <div className="selection-bar">
            <span>{selected.size} selected across the study</span>
            <button className="text-button" onClick={() => selectMany([])}>
              Clear selection
            </button>
          </div>
        )}
        <div className="table-scroll">
          <table className="run-table">
            <thead>
              <tr>
                <th className="check-cell">
                  <input
                    type="checkbox"
                    aria-label="Select this page"
                    checked={
                      pageRuns.length > 0 &&
                      pageRuns.every((r) => selected.has(r.key))
                    }
                    onChange={() => {
                      const keys = new Set(selected)
                      const all = pageRuns.every((r) => keys.has(r.key))
                      pageRuns.forEach((r) =>
                        all ? keys.delete(r.key) : keys.add(r.key),
                      )
                      selectMany([...keys])
                    }}
                  />
                </th>
                <th
                  aria-sort={
                    sort.id === 'run'
                      ? sort.descending
                        ? 'descending'
                        : 'ascending'
                      : 'none'
                  }
                >
                  <button onClick={() => setOrder('run')}>
                    Run{' '}
                    {sort.id === 'run' ? (sort.descending ? '↓' : '↑') : '↕'}
                  </button>
                </th>
                <th>Status</th>
                {tableColumns.map((c) => (
                  <th
                    key={c.id}
                    aria-sort={
                      sort.id === c.id
                        ? sort.descending
                          ? 'descending'
                          : 'ascending'
                        : 'none'
                    }
                  >
                    <button onClick={() => setOrder(c.id)}>
                      <small>
                        {c.scope}
                        {c.unit && c.unit !== '1' ? ` · ${c.unit}` : ''}
                      </small>
                      {c.label}{' '}
                      {sort.id === c.id ? (sort.descending ? '↓' : '↑') : '↕'}
                    </button>
                  </th>
                ))}
                <th>
                  <span className="sr-only">Recording</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {pageRuns.map((r) => (
                <tr
                  key={r.key}
                  className={selected.has(r.key) ? 'selected-row' : ''}
                >
                  <td className="check-cell">
                    <input
                      type="checkbox"
                      aria-label={`Select ${r.record.run_id}`}
                      checked={selected.has(r.key)}
                      onChange={() => toggle(r.key)}
                    />
                  </td>
                  <td>
                    <button
                      className="run-link"
                      title={r.source}
                      onClick={() => inspect(r.key)}
                    >
                      {r.record.run_id}
                      <span>↗</span>
                    </button>
                  </td>
                  <td>
                    <Status value={r.record.execution.status} />
                  </td>
                  {tableColumns.map((c) => (
                    <td
                      key={c.id}
                      className="number"
                      title={r.definitions[c.id]?.description}
                    >
                      {format(r.values[c.id])}
                    </td>
                  ))}
                  <td>
                    <span className="recording-tag">
                      {r.trajectory ? '≋ Recorded' : 'Summary'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!pageRuns.length && (
          <div className="empty">
            <h3>
              {runs.length
                ? 'No runs match these filters.'
                : 'No experiments found.'}
            </h3>
            <p>
              {runs.length
                ? 'Try a broader search or reset your filters.'
                : 'Open a study file or a directory containing recorded experiments.'}
            </p>
          </div>
        )}
        <div className="pagination">
          <span>
            Showing {sorted.length ? currentPage * 50 + 1 : 0}–
            {Math.min((currentPage + 1) * 50, sorted.length)} of{' '}
            {sorted.length.toLocaleString()} runs
          </span>
          <div>
            <button
              className="button"
              aria-label="Previous page"
              disabled={currentPage === 0}
              onClick={() => setPage(currentPage - 1)}
            >
              ←
            </button>
            <span>
              Page {currentPage + 1} / {pages}
            </span>
            <button
              className="button"
              aria-label="Next page"
              disabled={currentPage >= pages - 1}
              onClick={() => setPage(currentPage + 1)}
            >
              →
            </button>
          </div>
        </div>
      </section>
    </>
  )
}
