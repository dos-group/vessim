import { Fragment, useMemo } from 'react'
import { useViewer } from '../context.jsx'
import { columnGroups, cell, sample, numeric } from '../model.js'
import { summarize } from '../uncertainty.js'
import { fmt } from '../presentation.js'
import { visibleRows, toggle } from '../state.js'
import { resultPlot } from '../result-plots.js'
import { exportRows } from '../export.js'
import {
  Checkbox,
  ChoiceGroup,
  FieldSelect,
  Heading,
  Picker,
  Select,
  UnitSelect,
} from './controls.jsx'
import { Representation } from './Representation.jsx'
import { Reorderable } from './Ordering.jsx'
import { Chart } from './Chart.jsx'

function MetricCell({ entity, column }) {
  const { view: s, presentation: p } = useViewer()
  if (!entity.runs || column.kind === 'parameter')
    return p.metricText(column, cell(entity, column))
  const sampled = sample(entity, column)
  if (sampled.reason) return <span className="muted">{sampled.reason}</span>
  const values = sampled.points.map((p) => p.value),
    summary = summarize(values, s.stat, s.spread)
  return (
    <>
      {p.metricText(column, cell(entity, column, s.stat))}
      {summary.low !== null && values.length > 1 && (
        <small>
          {p.metricText(column, summary.low)}–
          {p.metricText(column, summary.high)} ·{' '}
          {s.spread === 'iqr' ? 'middle 50%' : 'range'}
        </small>
      )}
      <small>
        {values.length}/{entity.runs.length} runs
      </small>
    </>
  )
}
function ColumnsPicker() {
  const { study, view: s, patch, presentation: p } = useViewer()
  return (
    <Picker label="Columns">
      {columnGroups(study.columns, study.singleMicrogrid).map((group) => (
        <ChoiceGroup key={group.label} label={group.label}>
          {group.columns.map((c) => (
            <div className="column-option" key={c.id}>
              <Checkbox
                label={`${c.label}${p.unit(c) && p.unit(c) !== '1' ? ` (${p.unit(c)})` : ''}`}
                checked={s.visible.includes(c.id)}
                data-visible={c.id}
                onChange={(enabled) =>
                  patch((v) => ({
                    visible: enabled
                      ? [...v.visible, c.id]
                      : v.visible.filter((id) => id !== c.id),
                  }))
                }
              />
              {s.visible.includes(c.id) && (
                <UnitSelect
                  label={`Display unit for ${p.scopeLabel(c)} ${c.label}`}
                  unit={c.unit}
                  magnitude={s.magnitudes[c.id]}
                  value={s.units[c.id]}
                  data-unit={c.id}
                  onChange={(unit) =>
                    patch((v) => ({ units: { ...v.units, [c.id]: unit } }))
                  }
                />
              )}
            </div>
          ))}
        </ChoiceGroup>
      ))}
    </Picker>
  )
}
export function ConfigDetail({ configuration: c }) {
  const { patch, presentation: p, navigate } = useViewer()
  return (
    <section className="panel detail">
      <div className="detail-header">
        <h2>{c.name}</h2>
        <button
          aria-label="Close details"
          onClick={() => patch({ opened: null })}
        >
          ×
        </button>
      </div>
      <dl>
        {Object.entries(c.values).map(([key, value]) => (
          <Fragment key={key}>
            <dt>{p.field(key)?.label || key}</dt>
            <dd>{fmt(value)}</dd>
          </Fragment>
        ))}
      </dl>
      <h3>Runs</h3>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Run</th>
            </tr>
          </thead>
          <tbody>
            {c.runs.map((run) => (
              <tr key={run.key}>
                <td>
                  <button
                    className="link"
                    data-run={run.key}
                    onClick={() =>
                      navigate(`run/${encodeURIComponent(run.key)}`)
                    }
                  >
                    {run.key}
                  </button>
                  <small>{run.realization?.id || ''}</small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        onClick={() => {
          patch({ mode: 'runs', configFilter: [c.key], query: '', rowPage: 0 })
          navigate('results')
        }}
      >
        Inspect runs
      </button>
    </section>
  )
}
function ResultsPlot({ rows }) {
  const { study, view: s, patch, presentation: p } = useViewer()
  const fields = study.columns.filter(
    (c) =>
      c.numeric &&
      (s.mode === 'runs' ||
        c.kind === 'metric' ||
        study.configurations.some((e) => numeric(e.values[c.id]))),
  )
  const vertical =
    s.plotType === 'scatter'
      ? fields
      : fields.filter((c) => c.kind === 'metric')
  const x = fields.some((c) => c.id === s.x) ? s.x : fields[0]?.id
  const y = vertical.some((c) => c.id === s.y)
    ? s.y
    : vertical[1]?.id || vertical[0]?.id
  const current = useMemo(() => ({ ...s, x, y }), [s, x, y])
  const prepared = useMemo(
    () => resultPlot(study, current, rows),
    [study, current, rows],
  )
  const zoomKey = `${s.plotType}/${x}/${y}`
  const options = [
    {
      id: 'distribution',
      name: 'By configuration',
      description: 'Compare one metric',
    },
    {
      id: 'scatter',
      name: 'Scatter plot',
      description: 'Explore inputs and outcomes',
    },
    {
      id: 'ecdf',
      name: 'Distribution',
      description: study.singleRun
        ? 'Needs repeated runs'
        : 'Explore outcome frequencies',
    },
  ]
  return (
    <section className="panel plot-panel">
      <div className="result-views" role="group" aria-label="Results plot view">
        {options.map((option) => (
          <button
            key={option.id}
            data-plot-view={option.id}
            aria-pressed={s.plotType === option.id}
            disabled={option.id === 'ecdf' && study.singleRun}
            onClick={() => patch({ plotType: option.id })}
          >
            <strong>{option.name}</strong>
            <span>{option.description}</span>
          </button>
        ))}
      </div>
      <div
        className={`plot-controls ${s.plotType === 'scatter' ? '' : 'one-axis'}`}
      >
        {s.plotType === 'scatter' && (
          <FieldSelect
            label="Horizontal axis"
            id="x"
            value={x}
            onChange={(x) => patch({ x })}
            columns={fields}
            study={study}
            view={s}
            patch={patch}
            presentation={p}
          />
        )}
        <FieldSelect
          label={s.plotType === 'scatter' ? 'Vertical axis' : 'Metric'}
          id="y"
          value={y}
          onChange={(y) => patch({ y })}
          columns={vertical}
          study={study}
          view={s}
          patch={patch}
          presentation={p}
        />
      </div>
      <div className="plot-tools">
        {s.plotType === 'scatter' && (
          <div className="pareto-controls">
            <Checkbox
              id="pareto"
              label="Pareto front"
              checked={s.pareto}
              onChange={(pareto) => patch({ pareto })}
            />
            {s.pareto &&
              ['X', 'Y'].map((axis) => (
                <Select
                  key={axis}
                  id={`pareto${axis}`}
                  label={`${axis === 'X' ? 'Horizontal' : 'Vertical'} objective`}
                  value={s[`pareto${axis}`]}
                  onChange={(value) => patch({ [`pareto${axis}`]: value })}
                  options={[
                    { value: 'min', label: 'Minimize' },
                    { value: 'max', label: 'Maximize' },
                  ]}
                />
              ))}
          </div>
        )}
        <button onClick={() => patch({ plotZoom: [] })}>Reset zoom</button>
      </div>
      {prepared.option ? (
        <Chart
          id="scatter"
          label="Results chart"
          option={prepared.option}
          onSelect={(key) =>
            patch((v) => {
              const kind = v.mode === 'runs' ? 'runs' : 'configs'
              return { [kind]: toggle(v[kind], key) }
            })
          }
          onZoom={(plotZoom) => patch({ plotZoom, plotZoomKey: zoomKey })}
        />
      ) : (
        <p className="empty">{prepared.empty}</p>
      )}
      <p id="plot-note" className="plot-note">
        {prepared.note}
      </p>
    </section>
  )
}
function SortButton({ field, children }) {
  const { view: s, patch } = useViewer()
  return (
    <button
      className="sort"
      data-sort={field}
      onClick={() =>
        patch({
          sort: field,
          descending: s.sort === field ? !s.descending : false,
        })
      }
    >
      {children} {s.sort === field ? (s.descending ? '↓' : '↑') : '↕'}
    </button>
  )
}
export function Results() {
  const {
    study,
    view: s,
    patch,
    presentation: p,
    navigate,
    openTimeSeries,
  } = useViewer()
  const rows = useMemo(() => visibleRows(study, s), [study, s])
  const isRun = s.mode === 'runs',
    kind = isRun ? 'runs' : 'configs',
    selected = s[kind]
  const columns = s.visible.map(p.field).filter(Boolean),
    label = isRun && !study.singleRun ? 'Run' : 'Configuration'
  const pages = Math.max(1, Math.ceil(rows.length / 50)),
    page = Math.min(s.rowPage, pages - 1),
    shown = rows.slice(page * 50, (page + 1) * 50)
  return (
    <>
      <Heading title="Results">
        {study.name} · {study.configurations.length} configurations
        {study.singleRun ? '' : ` · ${study.runs.length} runs`}
      </Heading>
      {study.description && (
        <details className="study-details">
          <summary>Study details</summary>
          <p>{study.description}</p>
        </details>
      )}
      <div className="toolbar">
        <label className="inline-label">
          Search
          <input
            id="search"
            type="search"
            placeholder="Name, ID or parameter"
            value={s.query}
            onChange={(e) => patch({ query: e.target.value, rowPage: 0 })}
          />
        </label>
        <button onClick={() => patch({ plot: !s.plot })}>
          {s.plot ? 'Hide' : 'Show'} plot
        </button>
      </div>
      {s.configFilter.length > 0 && isRun && (
        <p className="filter-chip">
          Runs from {s.configFilter.length} selected configuration(s){' '}
          <button onClick={() => patch({ configFilter: [] })}>
            Show all runs
          </button>
        </p>
      )}
      <Representation />
      {s.plot && <ResultsPlot rows={rows} />}
      <div className="selection-toolbar">
        <span>
          {selected.size} {label.toLowerCase()}s selected
        </span>
        <button
          disabled={!selected.size}
          onClick={() => patch({ [kind]: new Set() })}
        >
          Clear
        </button>
        <button disabled={!selected.size} onClick={openTimeSeries}>
          Time series
        </button>
        <button onClick={() => exportRows(study, s, study.study_id)}>
          Export {selected.size ? 'selected' : 'filtered'}
        </button>
        <ColumnsPicker />
      </div>
      <div className="workspace">
        <section className="panel">
          <div className="scroll">
            <table className="results-table">
              <thead>
                <tr>
                  <th>
                    <div className="selection-sort">
                      <input
                        type="checkbox"
                        id="select-page"
                        aria-label="Select visible rows"
                        checked={
                          shown.length > 0 &&
                          shown.every((e) => selected.has(e.key))
                        }
                        onChange={(e) => {
                          const enabled = e.target.checked
                          patch((v) => {
                            let keys = v[kind]
                            for (const row of shown)
                              keys = toggle(keys, row.key, enabled)
                            return { [kind]: keys }
                          })
                        }}
                      />
                      <button
                        className="selected-first"
                        aria-label="Selected first"
                        title="Selected first"
                        aria-pressed={s.selectedFirst}
                        onClick={() =>
                          patch({ selectedFirst: !s.selectedFirst, rowPage: 0 })
                        }
                      >
                        ↑
                      </button>
                    </div>
                  </th>
                  <th>
                    <SortButton field="name">{label}</SortButton>
                  </th>
                  {!isRun && <th>Runs</th>}
                  {columns.map((c) => (
                    <Reorderable
                      as="th"
                      key={c.id}
                      itemKey={c.id}
                      kind="visible"
                      className={c.numeric ? 'number' : ''}
                      title="Drag to reorder or use Alt + arrow keys"
                    >
                      <SortButton field={c.id}>{c.label}</SortButton>
                      <small>
                        {p.scopeLabel(c)}
                        {c.unit ? ` · ${p.unit(c)}` : ''}
                      </small>
                    </Reorderable>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shown.map((e) => (
                  <Fragment key={e.key}>
                    <tr className={selected.has(e.key) ? 'selected-row' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          data-select={e.key}
                          aria-label={`Select ${e.name}`}
                          checked={selected.has(e.key)}
                          onChange={(event) => {
                            const checked = event.target.checked
                            patch((v) => ({
                              [kind]: toggle(v[kind], e.key, checked),
                            }))
                          }}
                        />
                      </td>
                      <td>
                        <button
                          className="link"
                          data-run={isRun ? e.key : undefined}
                          data-config={!isRun ? e.key : undefined}
                          onClick={() =>
                            isRun
                              ? navigate(`run/${encodeURIComponent(e.key)}`)
                              : patch({
                                  opened: s.opened === e.key ? null : e.key,
                                })
                          }
                        >
                          {e.name}
                        </button>
                        {isRun && !study.singleRun && (
                          <small>
                            {e.configuration.name}
                            {e.record.parameters.seed == null
                              ? ''
                              : ` · seed ${e.record.parameters.seed}`}
                          </small>
                        )}
                      </td>
                      {!isRun && <td>{e.runs.length}</td>}
                      {columns.map((c) => (
                        <td key={c.id} className={c.numeric ? 'number' : ''}>
                          <MetricCell entity={e} column={c} />
                        </td>
                      ))}
                    </tr>
                    {!isRun && s.opened === e.key && (
                      <tr className="expanded-config">
                        <td colSpan={columns.length + 3}>
                          <ConfigDetail configuration={e} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            {!rows.length && (
              <p className="empty">No matching completed results.</p>
            )}
          </div>
          <div className="table-footer">
            {rows.length} matching {label.toLowerCase()}s
            <span>
              <button
                aria-label="Previous page"
                disabled={page === 0}
                onClick={() => patch({ rowPage: page - 1 })}
              >
                ←
              </button>{' '}
              {page + 1} / {pages}{' '}
              <button
                aria-label="Next page"
                disabled={page + 1 >= pages}
                onClick={() => patch({ rowPage: page + 1 })}
              >
                →
              </button>
            </span>
          </div>
        </section>
      </div>
    </>
  )
}
