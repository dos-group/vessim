/* global echarts */
import {
  completedStudy,
  columnGroups,
  cell,
  sample,
  stable,
  numeric,
  human,
} from './model.js?v=analysis-10'
import {
  unitOptions,
  displayUnit,
  inDisplayUnit,
} from './units.js?v=analysis-10'
const main = document.querySelector('#main'),
  selector = document.querySelector('#study')
const studies = new Map(),
  states = new Map(),
  recordings = new Map()
const colors = [
  '#087f72',
  '#b65429',
  '#566bbb',
  '#a54c84',
  '#68802e',
  '#8c62b5',
  '#267f9c',
  '#a44747',
]
let active = new URLSearchParams(location.search).get('study') || 'recorded'
let generation = 0,
  charts = [],
  observers = []
const esc = (v) =>
  String(v ?? '').replace(
    /[&<>"']/g,
    (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[
        c
      ],
  )
const fmt = (v) =>
  v == null
    ? '—'
    : typeof v === 'number'
      ? v.toLocaleString('en-GB', { maximumSignificantDigits: 5 })
      : typeof v === 'object'
        ? JSON.stringify(v)
        : String(v)
const data = () => studies.get(active)
const page = () => location.hash.slice(1) || 'results'
const state = () => states.get(active)
const signalLabel = (signal) => {
  if (signal.field === 'p_grid') return 'Grid power'
  if (signal.field === 'p_delta') return 'Net actor power'
  const parts = signal.field
    .split('.')
    .map((s) => s.replaceAll('%2E', '.').replaceAll('%25', '%'))
  const label =
    {
      soc: 'State of charge',
      charge_level: 'Stored energy',
      power: 'Power',
      current_power: 'Power',
    }[parts.at(-1)] || human(parts.at(-1))
  return parts.length > 1
    ? `${parts.slice(1, -1).join(' / ') || human(parts[0])} / ${label}`
    : label
}
const field = (id) => data().columns.find((c) => c.id === id)
const fields = () => data().columns.filter((c) => c.kind === 'metric')
const spec = (c) =>
  displayUnit(c.unit, state().magnitudes[c.id], state().units[c.id])
const unit = (c) => spec(c).unit
const value = (c, v) => (c.kind === 'metric' ? inDisplayUnit(v, spec(c)) : v)
const metricText = (c, v) => fmt(value(c, v))
const columnLabel = (c) =>
  `${c.scope} · ${c.label}${unit(c) && unit(c) !== '1' ? ` (${unit(c)})` : ''}`
const selected = () => state()[state().mode === 'runs' ? 'runs' : 'configs']
const entities = () =>
  state().mode === 'runs' ? data().runs : data().configurations
const color = (run) => state().runColors[run.key]
function inSelectionOrder(items, keys) {
  const byKey = new Map(items.map((item) => [item.key, item]))
  return [...keys].map((key) => byKey.get(key)).filter(Boolean)
}
function moveSelection(keys, key, position) {
  const order = [...keys]
  const from = order.indexOf(key)
  if (from < 0) return
  order.splice(from, 1)
  order.splice(Math.max(0, Math.min(position, order.length)), 0, key)
  keys.clear()
  order.forEach((id) => keys.add(id))
}
function reorder(kind, key, position) {
  if (kind !== 'visible') return moveSelection(state()[kind], key, position)
  const order = new Set(state().visible)
  moveSelection(order, key, position)
  state().visible = [...order]
}
function assignRunColors() {
  const s = state()
  for (const key of Object.keys(s.runColors))
    if (!s.runs.has(key)) delete s.runColors[key]
  // Reserve existing colors before assigning new ones, regardless of order.
  const used = new Set(Object.values(s.runColors))
  for (const key of s.runs) {
    if (s.runColors[key]) continue
    s.runColors[key] = colors.find((c) => !used.has(c)) || colors[0]
    used.add(s.runColors[key])
  }
}
function orderControls(entries, kind) {
  if (!entries.length || entries.length > 8) return ''
  const isRun = kind === 'runs'
  return `<section class="selection-order" aria-label="${isRun ? 'Run' : 'Configuration'} order"><ol>${entries.map((e) => `<li data-order-key="${esc(e.key)}" data-kind="${kind}" tabindex="0" aria-label="${esc(e.name)}. Drag or use arrow keys to reorder." aria-keyshortcuts="ArrowLeft ArrowRight" title="Drag to reorder">${isRun ? `<i style="background:${color(e)}" aria-hidden="true"></i>` : ''}<span class="order-name">${esc(e.name)}</span><button data-remove-selection="${esc(e.key)}" data-kind="${kind}" aria-label="Remove ${esc(e.name)}" title="Remove">×</button></li>`).join('')}</ol></section>`
}
let drag = null
function cancelDrag() {
  if (!drag) return
  const { item, pointerId } = drag
  drag = null
  item.classList.remove('dragging')
  item.style.transform = ''
  if (item.hasPointerCapture(pointerId)) item.releasePointerCapture(pointerId)
  main
    .querySelectorAll('.drop-before, .drop-after')
    .forEach((el) => el.classList.remove('drop-before', 'drop-after'))
}
function focusSelection(key) {
  const item = [...main.querySelectorAll('[data-order-key]')].find(
    (item) => item.dataset.orderKey === key,
  )
  ;(item?.dataset.kind === 'visible'
    ? item.querySelector('button')
    : item
  )?.focus()
}
main.addEventListener('pointerdown', (event) => {
  const item = event.target.closest('[data-order-key]')
  if (
    !item ||
    (event.target.closest('button') && item.dataset.kind !== 'visible') ||
    event.button !== 0
  )
    return
  drag = {
    item,
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    key: item.dataset.orderKey,
    kind: item.dataset.kind,
    target: null,
    active: false,
  }
  if (drag.kind !== 'visible') item.setPointerCapture(event.pointerId)
})
main.addEventListener('pointermove', (event) => {
  if (!drag || event.pointerId !== drag.pointerId) return
  const dx = event.clientX - drag.x,
    dy = event.clientY - drag.y
  if (!drag.active && Math.hypot(dx, dy) < 6) return
  if (!drag.active) drag.item.setPointerCapture(event.pointerId)
  drag.active = true
  drag.item.classList.add('dragging')
  drag.item.style.transform = `translate(${dx}px, ${dy}px)`
  main
    .querySelectorAll('.drop-before, .drop-after')
    .forEach((el) => el.classList.remove('drop-before', 'drop-after'))
  const target = document
    .elementFromPoint(event.clientX, event.clientY)
    ?.closest('[data-order-key]')
  drag.target =
    target && target !== drag.item && target.dataset.kind === drag.kind
      ? target
      : null
  if (drag.target) {
    const keys = [...state()[drag.kind]]
    target.classList.add(
      keys.indexOf(target.dataset.orderKey) < keys.indexOf(drag.key)
        ? 'drop-before'
        : 'drop-after',
    )
  }
})
main.addEventListener('pointerup', (event) => {
  if (!drag || event.pointerId !== drag.pointerId) return
  const { key, kind, target, active } = drag
  cancelDrag()
  if (!active || !target) return
  const keys = state()[kind]
  reorder(kind, key, [...keys].indexOf(target.dataset.orderKey))
  render()
  focusSelection(key)
})
main.addEventListener('pointercancel', cancelDrag)
main.addEventListener('lostpointercapture', cancelDrag)
main.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    cancelDrag()
    return
  }
  const item = event.target.closest('[data-order-key]')
  if (
    !item ||
    (item.dataset.kind === 'visible'
      ? !event.altKey
      : event.target.closest('button')) ||
    !['ArrowLeft', 'ArrowRight'].includes(event.key)
  )
    return
  event.preventDefault()
  const keys = state()[item.dataset.kind],
    key = item.dataset.orderKey
  reorder(
    item.dataset.kind,
    key,
    [...keys].indexOf(key) + (event.key === 'ArrowLeft' ? -1 : 1),
  )
  render()
  focusSelection(key)
})
const count = (c) => String(c.runs.length)
const option = (value, label, current) =>
  `<option value="${esc(value)}" ${value === current ? 'selected' : ''}>${esc(label)}</option>`
const options = (columns, current) =>
  columns.map((c) => option(c.id, columnLabel(c), current)).join('')
const route = (next) => {
  if (page() === next) render()
  else location.hash = next
}
function initState(study) {
  const metrics = study.columns.filter((c) => c.kind === 'metric')
  // Prefer non-constant recorded metrics; no metric name is required by the UI.
  const varying = metrics.filter(
    (c) => new Set(study.runs.map((r) => r.values[c.id])).size > 1,
  )
  const defaults = [
    ...varying.filter((c) => c.scope === 'Run'),
    ...varying.filter((c) => c.scope !== 'Run'),
  ]
  // Example-specific initial axes; all recorded fields remain selectable.
  if (study.study_id?.startsWith('infrastructure-')) {
    const preferred = ['initial embodied emissions', 'grid emissions']
    defaults.sort((a, b) => {
      const rank = (c) => {
        const i = preferred.indexOf(c.label)
        return i < 0 ? preferred.length : i
      }
      return rank(a) - rank(b)
    })
  }
  return {
    mode: 'runs',
    runColors: {},
    units: {},
    magnitudes: Object.fromEntries(
      study.columns.map((c) => [
        c.id,
        study.runs.reduce(
          (max, r) =>
            numeric(r.values[c.id])
              ? Math.max(max, Math.abs(r.values[c.id]))
              : max,
          0,
        ),
      ]),
    ),
    runs: new Set(),
    configs: new Set(),
    query: '',
    configFilter: [],
    stat: '',
    x: defaults[0]?.id,
    y: defaults[1]?.id || defaults[0]?.id,
    visible: [
      ...study.columns
        .filter((c) => c.kind === 'parameter')
        .slice(0, 3)
        .map((c) => c.id),
      ...defaults.slice(0, 3).map((c) => c.id),
    ],
    sort: 'name',
    descending: false,
    selectedFirst: false,
    zoom: { start: 0, end: 100 },
    signals: null,
    alignment: 'elapsed',
    plot: true,
    opened: null,
    rowPage: 0,
  }
}
async function load(id) {
  active = id
  selector.value = id
  const token = ++generation
  if (studies.has(id)) {
    render()
    return
  }
  disposeCharts()
  main.innerHTML = '<p role="status">Loading recorded summaries…</p>'
  try {
    const origin = new URL(
      `../../results/viewer-proposal/${id}/study.json`,
      location.href,
    )
    const response = await fetch(origin)
    if (!response.ok)
      throw new Error(
        'Example data unavailable. Run viewer/design/generate_recorded.py and viewer/design/generate_fixtures.py.',
      )
    const raw = await response.json()
    await Promise.all(
      raw.configurations.flatMap((c) =>
        c.runs.map(async (r) => {
          const url = new URL(r.path, origin)
          const result = await fetch(url)
          if (!result.ok) throw new Error(`Run unavailable: ${r.run_id}`)
          r.record = await result.json()
          if (r.record.run_id !== r.run_id)
            throw new Error(`Run identity mismatch: ${r.run_id}`)
          r.trajectoryUrl =
            typeof r.record.timeseries === 'string'
              ? new URL(r.record.timeseries, url).href
              : null
        }),
      ),
    )
    const study = completedStudy(raw)
    studies.set(id, study)
    if (!states.has(id)) states.set(id, initState(study))
    if (token === generation) render()
  } catch (e) {
    if (token === generation)
      main.innerHTML = `<h1>Could not open study</h1><p>${esc(e.message)}</p>`
  }
}
function disposeCharts() {
  echarts.disconnect('prototype-time')
  observers.forEach((o) => o.disconnect())
  observers = []
  charts.forEach((c) => c.dispose())
  charts = []
}
function chart(target, option, onClick, group) {
  const element = document.querySelector(target)
  if (!element) return
  const c = echarts.init(element)
  c.setOption({
    animation: false,
    textStyle: { fontFamily: 'system-ui', fontSize: 12 },
    grid: { left: 80, right: 30, top: 35, bottom: 65 },
    tooltip: { renderMode: 'richText', confine: true },
    ...option,
  })
  if (onClick) c.on('click', onClick)
  if (group) c.group = group
  const observer = new ResizeObserver(() => c.resize())
  observer.observe(element)
  observers.push(observer)
  charts.push(c)
  return c
}
let renderedView = ''
function render() {
  if (!data()) return
  if (page() === 'compare') history.replaceState(null, '', '#results')
  const view = `${active}/${page()}`
  const navigated = renderedView !== view
  renderedView = view
  cancelDrag()
  disposeCharts()
  assignRunColors()
  for (const item of ['results', 'timeseries'])
    document
      .querySelector(`#${item}-nav`)
      .classList.toggle(
        'active',
        page() === item || (item === 'results' && page().startsWith('run/')),
      )
  document.querySelector('#run-count').textContent = state().runs.size
  if (page() === 'proposal')
    main.innerHTML = document.querySelector('#proposal').innerHTML
  else if (page() === 'timeseries') renderTimeSeries()
  else if (page().startsWith('run/'))
    renderRun(decodeURIComponent(page().slice(4)))
  else renderResults()
  if (navigated) window.scrollTo(0, 0)
}
function modeControl() {
  if (data().singleRun) return ''
  return `<div class="segmented" role="group" aria-label="Analysis level"><button data-mode="configurations" aria-pressed="${state().mode === 'configurations'}">Configurations</button><button data-mode="runs" aria-pressed="${state().mode === 'runs'}">Runs</button></div>`
}
function summaryControl() {
  return !data().singleRun && state().mode === 'configurations'
    ? `<label class="inline-label">Metric summary<select id="stat">${option('', 'Choose a statistic…', state().stat)}${['median', 'mean', 'min', 'max'].map((s) => option(s, `${human(s)} · completed runs`, state().stat)).join('')}</select></label>`
    : ''
}
function header(title) {
  return `<div class="heading"><div><h1>${esc(title)}</h1><p>${esc(data().name)} · ${data().configurations.length} configurations${data().singleRun ? '' : ` · ${data().runs.length} runs`}</p></div>${modeControl()}</div>`
}
function visibleRows() {
  const s = state()
  const rows = entities().filter((e) => {
    if (
      s.query &&
      !`${e.key} ${e.name} ${JSON.stringify(e.runs ? e.parameters : e.record.parameters)}`
        .toLowerCase()
        .includes(s.query.toLowerCase())
    )
      return false
    if (
      s.mode === 'runs' &&
      s.configFilter.length &&
      !s.configFilter.includes(e.configuration.key)
    )
      return false
    return true
  })
  return rows.sort((a, b) => {
    if (s.selectedFirst) {
      const group = Number(selected().has(b.key)) - Number(selected().has(a.key))
      if (group) return group
    }
    const col = field(s.sort),
      av = col ? cell(a, col, s.stat) : a.name,
      bv = col ? cell(b, col, s.stat) : b.name
    if (av == null) return bv == null ? 0 : 1
    if (bv == null) return -1
    const n =
      numeric(av) && numeric(bv)
        ? av - bv
        : String(av).localeCompare(String(bv), undefined, { numeric: true })
    return s.descending ? -n : n
  })
}
function displayCell(entity, col) {
  if (!entity.runs || col.kind === 'parameter')
    return esc(metricText(col, cell(entity, col)))
  const s = sample(entity, col)
  if (s.reason) return `<span class="muted">${esc(s.reason)}</span>`
  const values = s.points.map((p) => p.value)
  const text = state().stat
    ? metricText(col, cell(entity, col, state().stat))
    : values.length
      ? values.length === 1
        ? metricText(col, values[0])
        : `${metricText(col, Math.min(...values))}–${metricText(col, Math.max(...values))}`
      : '—'
  return `${text}<small>${values.length}/${entity.runs.length} values${!state().stat && values.length > 1 ? ' · range' : ''}</small>`
}
function columnPicker(ids, columns) {
  return `<details class="column-picker"><summary class="button">Columns</summary><div class="picker-options">${columnGroups(columns).map(group => `<fieldset class="column-group"><legend>${esc(group.label)}</legend>${group.columns
    .map(
      (c) =>
        `<div class="column-option"><label><input type="checkbox" data-visible="${esc(c.id)}" ${ids.includes(c.id) ? 'checked' : ''}>${esc(c.label)}${unit(c) && unit(c) !== '1' ? ` (${esc(unit(c))})` : ''}</label>${
          ids.includes(c.id) && unitOptions(c.unit).length > 1
            ? `<select data-unit="${esc(c.id)}" aria-label="Display unit for ${esc(c.scope)} ${esc(c.label)}">${option('auto', `Auto (${displayUnit(c.unit, state().magnitudes[c.id]).unit})`, state().units[c.id] || 'auto')}${unitOptions(
                c.unit,
              )
                .map((u) =>
                  option(u.unit, u.unit, state().units[c.id] || 'auto'),
                )
                .join('')}</select>`
            : ''
        }</div>`,
    )
    .join('')}</fieldset>`).join('')}</div></details>`
}
function renderResults() {
  const s = state(),
    rows = visibleRows(),
    isRun = s.mode === 'runs',
    columns = s.visible.map(field).filter(Boolean),
    label = isRun && !data().singleRun ? 'Run' : 'Configuration'
  const numericFields = data().columns.filter(
    (c) =>
      c.numeric &&
      (isRun ||
        c.kind === 'metric' ||
        data().configurations.some((e) => numeric(e.values[c.id]))),
  )
  if (!numericFields.some((c) => c.id === s.x)) s.x = numericFields[0]?.id
  if (!numericFields.some((c) => c.id === s.y))
    s.y = numericFields[1]?.id || s.x
  s.rowPage = Math.min(s.rowPage, Math.max(0, Math.ceil(rows.length / 50) - 1))
  const shown = rows.slice(s.rowPage * 50, (s.rowPage + 1) * 50)
  main.innerHTML = `${header('Results')}${data().description ? `<details class="study-details"><summary>Study details</summary><p>${esc(data().description)}</p></details>` : ''}
  <div class="toolbar"><label class="inline-label">Search<input id="search" type="search" placeholder="Name, ID or parameter" value="${esc(s.query)}"></label>${summaryControl()}<button data-action="plot">${s.plot ? 'Hide' : 'Show'} plot</button></div>
  ${s.configFilter.length && isRun ? `<p class="filter-chip">Runs from ${s.configFilter.length} selected configuration(s) <button data-action="all-runs">Show all runs</button></p>` : ''}
  ${s.plot ? `<section class="panel plot-panel"><div class="plot-controls"><label>Horizontal axis<select id="x">${options(numericFields, s.x)}</select></label><label>Vertical axis<select id="y">${options(numericFields, s.y)}</select></label></div><div id="scatter" class="scatter" aria-label="Results scatter plot"></div><p id="plot-note" class="plot-note"></p></section>` : ''}
  <div class="selection-toolbar"><span>${selected().size} ${label.toLowerCase()}s selected</span><button data-action="clear" ${!selected().size ? 'disabled' : ''}>Clear</button><button data-action="${isRun ? 'time' : 'drill'}" ${!selected().size ? 'disabled' : ''}>${isRun ? 'Time series' : 'Inspect runs'}</button><button data-action="export">Export ${selected().size ? 'selected' : 'filtered'}</button>${columnPicker(s.visible, data().columns)}</div>
  <div class="workspace ${s.opened && !isRun ? 'with-detail' : ''}"><section class="panel"><div class="scroll"><table class="results-table"><thead><tr><th><div class="selection-sort"><input type="checkbox" id="select-page" aria-label="Select visible rows" ${shown.length && shown.every((e) => selected().has(e.key)) ? 'checked' : ''}><button class="selected-first" data-action="selected-first" aria-label="Selected first" title="Selected first" aria-pressed="${s.selectedFirst}"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 13V3m-3 3 3-3 3 3M9 4h6M9 8h4M9 12h2"/></svg></button></div></th><th><button class="sort" data-sort="name">${label} ${s.sort === 'name' ? (s.descending ? '↓' : '↑') : '↕'}</button></th>${isRun ? '' : '<th>Runs</th>'}${columns.map((c) => `<th data-order-key="${esc(c.id)}" data-kind="visible" title="Drag to reorder; click to sort"><button class="sort" aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight" data-sort="${esc(c.id)}">${esc(c.label)} ${s.sort === c.id ? (s.descending ? '↓' : '↑') : '↕'}</button><small>${esc(c.scope)}${c.unit ? ` · ${esc(unit(c))}` : ''}</small></th>`).join('')}</tr></thead><tbody>${shown.map((e) => `<tr class="${selected().has(e.key) ? 'selected-row' : ''}"><td><input type="checkbox" data-select="${esc(e.key)}" aria-label="Select ${esc(e.name)}" ${selected().has(e.key) ? 'checked' : ''}></td><td><button class="link" ${isRun ? `data-run="${esc(e.key)}"` : `data-config="${esc(e.key)}"`}>${esc(e.name)}</button>${isRun ? `<small>${esc(data().singleRun ? e.key : e.configuration.name)}</small>` : ''}</td>${isRun ? '' : `<td>${count(e)}</td>`}${columns.map((c) => `<td class="number">${displayCell(e, c)}</td>`).join('')}</tr>`).join('')}</tbody></table>${!rows.length ? '<p class="empty">No matching completed results.</p>' : ''}</div><div class="table-footer">${rows.length} matching ${label.toLowerCase()}s<span><button data-action="prev" ${s.rowPage === 0 ? 'disabled' : ''}>←</button> ${s.rowPage + 1} / ${Math.max(1, Math.ceil(rows.length / 50))} <button data-action="next" ${(s.rowPage + 1) * 50 >= rows.length ? 'disabled' : ''}>→</button></span></div></section>${s.opened && !isRun ? configDetail(data().configurations.find((c) => c.key === s.opened)) : ''}</div>`
  if (s.plot) renderScatter(rows)
}
function renderScatter(rows) {
  const s = state(),
    x = field(s.x),
    y = field(s.y),
    note = document.querySelector('#plot-note')
  if (!x || !y) {
    note.textContent = 'No numeric parameters or metrics recorded.'
    return
  }
  if (
    s.mode === 'configurations' &&
    !s.stat &&
    [x, y].some((c) => c.kind === 'metric')
  ) {
    document.querySelector('#scatter').innerHTML =
      '<div class="empty">Choose a metric summary above to plot one point per configuration, or switch to Runs to plot recorded values directly.</div>'
    return
  }
  const points = rows
    .map((e) => ({
      name: e.name,
      key: e.key,
      value: [value(x, cell(e, x, s.stat)), value(y, cell(e, y, s.stat))],
    }))
    .filter((p) => p.value.every(numeric))
  note.textContent = `${points.length} points · ${rows.length - points.length} omitted for missing or incompatible values. Click a point to select it; use the table to open details.${s.mode === 'configurations' ? ` ${human(s.stat)} of completed runs; counts are shown in the table.` : ''}`
  const definitionsVary = [x, y].some(
    (c) =>
      c.kind === 'metric' &&
      new Set(
        data()
          .runs.filter((r) => numeric(r.values[c.id]))
          .map((r) => stable(r.definitions[c.id])),
      ).size > 1,
  )
  if (definitionsVary)
    note.textContent +=
      ' Recorded metric definitions vary; review assumptions in run details.'
  chart(
    '#scatter',
    {
      tooltip: { trigger: 'item', renderMode: 'richText', confine: true },
      grid: { left: 85, right: 35, top: 28, bottom: 65 },
      xAxis: {
        type: 'value',
        name: `${x.label}${unit(x) ? ` (${unit(x)})` : ''}`,
        nameLocation: 'middle',
        nameGap: 38,
        scale: true,
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        name: `${y.label}${unit(y) ? ` (${unit(y)})` : ''}`,
        nameGap: 14,
        scale: true,
        splitLine: { lineStyle: { color: '#e4e9e6' } },
      },
      series: [
        {
          type: 'scatter',
          data: points.map((p) => ({
            ...p,
            symbolSize: selected().has(p.key) ? 12 : 8,
            itemStyle: {
              color: selected().has(p.key) ? '#b65429' : '#087f72',
              opacity: 0.8,
            },
          })),
        },
      ],
    },
    (event) => {
      const key = event.data?.key
      if (key) {
        if (selected().has(key)) selected().delete(key)
        else selected().add(key)
        render()
      }
    },
  )
}
function configDetail(c) {
  if (!c) return ''
  return `<section class="panel detail"><div class="detail-header"><h2>${esc(c.name)}</h2><button data-action="close" aria-label="Close details">×</button></div><dl>${Object.entries(
    c.parameters,
  )
    .map(([k, v]) => `<dt>${esc(human(k))}</dt><dd>${esc(fmt(v))}</dd>`)
    .join(
      '',
    )}</dl><h3>Runs</h3><div class="scroll"><table><thead><tr><th>Run</th></tr></thead><tbody>${c.runs.map((r) => `<tr><td><button class="link" data-run="${esc(r.key)}">${esc(r.key)}</button><small>${esc(r.realization?.id || '')}</small></td></tr>`).join('')}</tbody></table></div><button data-drill="${esc(c.key)}">Inspect runs</button></section>`
}
function renderRun(key) {
  const run = data().runs.find((r) => r.key === key)
  if (!run) {
    main.innerHTML =
      '<h1>Run unavailable</h1><a href="#results">Back to results</a>'
    return
  }
  main.innerHTML = `<p class="breadcrumb"><a href="#results">${esc(data().name)}</a> / <button class="link" data-drill="${esc(run.configuration.key)}">${esc(run.configuration.name)}</button> / ${esc(key)}</p><div class="heading"><div><h1>${esc(key)}</h1><p>${esc(run.realization?.id || 'No realization ID')}</p></div><button data-add-time="${esc(key)}">${run.trajectoryUrl ? 'Add to time series' : 'Inspect recording availability'}</button></div>
  <section class="panel scroll"><table><thead><tr><th>Metric / scope</th><th>Recorded value</th><th>Description & assumptions</th></tr></thead><tbody>${fields()
    .filter((c) => c.id in run.values)
    .map(
      (c) =>
        `<tr><th>${esc(c.label)}<small>${esc(c.scope)}</small></th><td class="number">${esc(metricText(c, run.values[c.id]))} ${esc(unit(c))}</td><td>${esc(run.definitions[c.id]?.description || '')}<details><summary>Assumptions</summary><pre>${esc(JSON.stringify(run.definitions[c.id]?.assumptions || {}, null, 2))}</pre></details></td></tr>`,
    )
    .join(
      '',
    )}</tbody></table></section><details><summary>Configuration and execution</summary><pre>${esc(JSON.stringify({ parameters: run.record.parameters, config: run.record.config, execution: run.record.execution }, null, 2))}</pre></details>`
}
function recording(run) {
  return recordings.get(`${active}/${run.key}`)
}
function ensureRecording(run) {
  if (!run.trajectoryUrl || recording(run)) return
  const key = `${active}/${run.key}`,
    entry = { pending: true }
  recordings.set(key, entry)
  const worker = new Worker(
    new URL('./recording.worker.js?v=analysis-10', import.meta.url),
  )
  const finish = (value) => {
    recordings.set(key, value)
    worker.terminate()
    if (page() === 'timeseries' && key.startsWith(`${active}/`)) render()
  }
  worker.onmessage = (event) => finish(event.data)
  worker.onerror = () => finish({ error: 'The recording could not be parsed.' })
  worker.postMessage({ url: run.trajectoryUrl })
}
function renderTimeSeries() {
  const s = state(),
    runs = inSelectionOrder(data().runs, s.runs)
  const pool = s.configs.size
    ? data().runs.filter((r) => s.configs.has(r.configuration.key))
    : data().runs
  main.innerHTML = `<div class="heading"><div><h1>Time series</h1><p>${esc(data().name)} · ${runs.length} selected runs</p></div><a class="button" href="#results">Back to results</a></div><div class="toolbar"><details class="column-picker"><summary class="button">Choose runs (${runs.length})</summary><div class="picker-options">${pool.map((r) => `<label><input type="checkbox" data-time-run="${esc(r.key)}" ${s.runs.has(r.key) ? 'checked' : ''}>${esc(r.key)}${!r.trajectoryUrl ? ' · no recording' : ''}</label>`).join('')}</div></details><label class="inline-label">Time alignment<select id="alignment">${option('elapsed', 'Elapsed from simulation start (h)', s.alignment)}${option('absolute', 'Recorded time (UTC)', s.alignment)}</select></label><button data-action="reset-zoom">Reset zoom</button><button data-action="clear-runs" ${!runs.length ? 'disabled' : ''}>Clear runs</button></div>
  ${s.configs.size ? `<p class="note">Run picker shows ${pool.length} runs from selected configurations. <button class="link" data-action="all-picker-runs">Show all study runs</button></p>` : ''}`
  main.innerHTML += orderControls(runs, 'runs')
  if (!runs.length) {
    main.innerHTML +=
      '<p class="empty">Choose individual runs to overlay. Configuration trajectories are not averaged.</p>'
    return
  }
  if (runs.length > 8) {
    main.innerHTML +=
      '<p class="empty">Choose up to eight runs for readable trajectory overlays.</p>'
    return
  }
  runs.forEach(ensureRecording)
  const notices = runs.flatMap((r) =>
    !r.trajectoryUrl
      ? [`${r.key}: no trajectory was recorded.`]
      : recording(r)?.error
        ? [`${r.key}: ${recording(r).error}`]
        : [],
  )
  main.innerHTML += notices
    .map((n) => `<p class="notice">${esc(n)}</p>`)
    .join('')
  if (runs.some((r) => recording(r)?.pending)) {
    main.innerHTML += '<p role="status">Loading selected recordings…</p>'
    return
  }
  const loaded = runs.filter((r) => recording(r)?.series)
  if (!loaded.length) return
  const signals = new Map()
  loaded.forEach((r) =>
    recording(r).series.forEach((sig) => signals.set(sig.id, sig)),
  )
  if (s.signals === null)
    s.signals = [...signals.values()]
      .filter((sig) => sig.field === 'p_grid' || sig.field.endsWith('.soc'))
      .slice(0, 3)
      .map((sig) => sig.id)
  const chosen = (s.signals || []).filter((id) => signals.has(id))
  main.innerHTML += `<div class="toolbar"><details class="column-picker"><summary class="button">Signals (${chosen.length})</summary><div class="picker-options">${[...signals.values()].map((sig) => `<label><input type="checkbox" data-signal="${esc(sig.id)}" ${chosen.includes(sig.id) ? 'checked' : ''}>${esc(sig.grid)} · ${esc(signalLabel(sig))} (${esc(sig.unit)})</label>`).join('')}</div></details><details class="column-picker"><summary class="button">Download CSV</summary><div class="picker-options">${loaded.map((r) => `<a href="${esc(r.trajectoryUrl)}" download>${esc(r.key)}</a>`).join('')}</div></details></div>`
  for (const r of loaded) {
    const rec = recording(r)
    if (rec.malformed)
      main.innerHTML += `<p class="notice">${esc(r.key)}: ${rec.malformed} malformed rows skipped.</p>`
    if (rec.series.some((sig) => sig.count > sig.points.length))
      main.innerHTML +=
        '<p class="note">Large signals use an extrema-preserving overview. Download CSV for full resolution.</p>'
  }
  if (!chosen.length) {
    main.innerHTML += '<p class="empty">Choose signals to plot.</p>'
    return
  }
  const jobs = []
  chosen.forEach((id, i) => {
    const signal = signals.get(id),
      matches = loaded.map((r) => ({
        run: r,
        signal: recording(r).series.find(
          (sig) => sig.id === id && sig.unit === signal.unit,
        ),
      }))
    const missing = matches.filter((m) => !m.signal).map((m) => m.run.key)
    const supported = matches.filter((m) => m.signal)
    const unit = signal.unit === '1' ? 'fraction' : signal.unit
    const error =
      signal.unit === 'unknown' && supported.length > 1
        ? 'Unit not recorded. Select a single run to inspect this signal.'
        : s.alignment === 'elapsed' &&
            supported.some(
              (m) =>
                !Number.isFinite(
                  time(m.run.record.config.environment?.sim_start),
                ),
            )
          ? 'Simulation start missing. Use recorded UTC time.'
          : ''
    main.innerHTML += `<section class="panel trajectory-panel"><div class="chart-heading"><h2>${esc(signalLabel(signal))}</h2><span>${esc(signal.grid)} · ${esc(unit)}</span></div>${missing.length ? `<p class="note">Signal missing in: ${esc(missing.join(', '))}</p>` : ''}${error ? `<p class="notice">${error}</p>` : `<div id="signal-${i}" class="time-chart" aria-label="${esc(signal.field)} trajectory chart"></div>`}</section>`
    if (!error)
      jobs.push(() =>
        chart(
          `#signal-${i}`,
          {
            useUTC: true,
            tooltip: { trigger: 'axis', renderMode: 'richText', confine: true },
            axisPointer: { link: [{ xAxisIndex: 'all' }] },
            grid: { top: 20, left: 80, right: 30, bottom: 75 },
            xAxis: {
              type: s.alignment === 'elapsed' ? 'value' : 'time',
              name: s.alignment === 'elapsed' ? 'Hours' : 'UTC',
              nameGap: 35,
              nameLocation: 'middle',
            },
            yAxis: {
              type: 'value',
              scale: true,
              splitLine: { lineStyle: { color: '#e5e9e7' } },
            },
            dataZoom: [
              { type: 'inside', filterMode: 'none', ...s.zoom },
              {
                type: 'slider',
                bottom: 4,
                height: 18,
                filterMode: 'none',
                ...s.zoom,
              },
            ],
            series: supported.map(({ run, signal: sig }) => ({
              id: run.key,
              name: run.name,
              type: 'line',
              step: 'end',
              showSymbol: false,
              connectNulls: false,
              lineStyle: { width: 1.6, color: color(run) },
              itemStyle: { color: color(run) },
              data: sig.points.map(([t, v]) => [
                s.alignment === 'elapsed'
                  ? (t - time(run.record.config.environment?.sim_start)) /
                    3600000
                  : t,
                v,
              ]),
            })),
          },
          null,
          'prototype-time',
        ),
      )
  })
  jobs.forEach((job) => job())
  charts.forEach((c) =>
    c.on('datazoom', () => {
      const { start, end } = c.getOption().dataZoom[0]
      s.zoom = { start, end }
    }),
  )
  echarts.connect('prototype-time')
}
function time(raw) {
  if (typeof raw !== 'string') return NaN
  let s = raw.replace(' ', 'T')
  if (/^\d{4}-\d\d-\d\d$/.test(s)) s += 'T00:00:00'
  return Date.parse(/(?:Z|[+-]\d\d:?\d\d)$/.test(s) ? s : s + 'Z')
}
function exportRows() {
  const cols = state().visible.map(field).filter(Boolean),
    rows = selected().size
      ? inSelectionOrder(entities(), selected())
      : visibleRows()
  const escape = (v) => {
    let t = fmt(v)
    if (v == null) t = ''
    if (typeof v !== 'number' && /^[=+\-@\t\r]/.test(t)) t = "'" + t
    return '"' + t.replaceAll('"', '""') + '"'
  }
  const lines = [
    ['id', 'configuration', 'summary', ...cols.map(columnLabel)],
    ...rows.map((e) => [
      e.key,
      e.runs ? e.key : e.configuration.key,
      e.runs ? state().stat || 'observed range' : 'recorded',
      ...cols.map((c) => {
        if (!e.runs || c.kind === 'parameter' || state().stat)
          return value(c, cell(e, c, state().stat))
        const values = sample(e, c).points.map((p) => value(c, p.value))
        return values.length
          ? values.length === 1
            ? values[0]
            : `${Math.min(...values)}–${Math.max(...values)}`
          : null
      }),
    ]),
  ]
  const url = URL.createObjectURL(
      new Blob([lines.map((row) => row.map(escape).join(',')).join('\r\n')], {
        type: 'text/csv',
      }),
    ),
    a = document.createElement('a')
  a.href = url
  a.download = `${active}-${data().singleRun ? 'configurations' : state().mode}.csv`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
main.addEventListener('input', (event) => {
  if (event.target.id !== 'search') return
  const position = event.target.selectionStart
  state().query = event.target.value
  state().rowPage = 0
  render()
  const input = document.querySelector('#search')
  input.focus()
  input.setSelectionRange(position, position)
})
function refreshPicker(input) {
  const oldPicker = input.closest('.column-picker'),
    label = oldPicker.querySelector('summary').textContent,
    scroll = oldPicker.querySelector('.picker-options').scrollTop,
    attribute = input.hasAttribute('data-unit') ? 'data-unit' : 'data-visible',
    key = input.getAttribute(attribute)
  render()
  const picker = [...main.querySelectorAll('.column-picker')].find(
    (p) => p.querySelector('summary').textContent === label,
  )
  if (!picker) return
  picker.open = true
  ;[...picker.querySelectorAll(`[${attribute}]`)]
    .find((control) => control.getAttribute(attribute) === key)
    ?.focus({ preventScroll: true })
  picker.querySelector('.picker-options').scrollTop = scroll
}
main.addEventListener('change', (event) => {
  const e = event.target,
    s = state()
  if (e.dataset.unit) {
    s.units[e.dataset.unit] = e.value
    refreshPicker(e)
    return
  }
  if (['x', 'y', 'stat', 'alignment'].includes(e.id)) {
    s[e.id] = e.value
    s.rowPage = 0
  } else if (e.id === 'select-page') {
    visibleRows()
      .slice(s.rowPage * 50, (s.rowPage + 1) * 50)
      .forEach((row) => {
        if (e.checked) selected().add(row.key)
        else selected().delete(row.key)
      })
  } else if (e.dataset.select) {
    if (e.checked) selected().add(e.dataset.select)
    else selected().delete(e.dataset.select)
  } else if (e.dataset.visible) {
    const id = e.dataset.visible
    s.visible = e.checked ? [...s.visible, id] : s.visible.filter((v) => v !== id)
    refreshPicker(e)
    return
  } else if (e.dataset.timeRun) {
    if (e.checked) s.runs.add(e.dataset.timeRun)
    else s.runs.delete(e.dataset.timeRun)
  } else if (e.dataset.signal) {
    s.signals = e.checked
      ? [...(s.signals || []), e.dataset.signal]
      : (s.signals || []).filter((id) => id !== e.dataset.signal)
  } else return
  render()
  if (e.dataset.timeRun)
    document.querySelector('.column-picker')?.setAttribute('open', '')
  if (e.dataset.signal)
    [...document.querySelectorAll('.column-picker')]
      .find((d) => d.textContent.startsWith('Signals'))
      ?.setAttribute('open', '')
})
main.addEventListener('click', (event) => {
  const e = event.target.closest('button')
  if (!e) return
  const s = state(),
    action = e.dataset.action
  if (e.dataset.removeSelection) {
    s[e.dataset.kind].delete(e.dataset.removeSelection)
    render()
    main.querySelector('[data-order-key]')?.focus()
    return
  }
  if (e.dataset.mode) {
    s.mode = e.dataset.mode
    s.rowPage = 0
    render()
    return
  }
  if (e.dataset.sort) {
    s.descending = s.sort === e.dataset.sort ? !s.descending : false
    s.sort = e.dataset.sort
    render()
    return
  }
  if (e.dataset.run) {
    route('run/' + encodeURIComponent(e.dataset.run))
    return
  }
  if (e.dataset.config) {
    s.opened = e.dataset.config
    render()
    return
  }
  if (e.dataset.drill) {
    s.mode = 'runs'
    s.configFilter = [e.dataset.drill]
    s.query = ''
    route('results')
    return
  }
  if (e.dataset.addTime) {
    s.runs.add(e.dataset.addTime)
    route('timeseries')
    return
  }
  if (action === 'selected-first') {
    s.selectedFirst = !s.selectedFirst
    s.rowPage = 0
    render()
    main.querySelector('[data-action="selected-first"]')?.focus()
    return
  }
  if (action === 'clear') selected().clear()
  else if (action === 'clear-runs') s.runs.clear()
  else if (action === 'close') s.opened = null
  else if (action === 'plot') s.plot = !s.plot
  else if (action === 'prev') s.rowPage = Math.max(0, s.rowPage - 1)
  else if (action === 'next') s.rowPage++
  else if (action === 'all-runs') s.configFilter = []
  else if (action === 'all-picker-runs') s.configs.clear()
  else if (action === 'time') {
    route('timeseries')
    return
  } else if (action === 'drill') {
    s.configFilter = [...s.configs]
    s.mode = 'runs'
    s.query = ''
    s.rowPage = 0
    route('results')
    return
  } else if (action === 'export') {
    exportRows()
    return
  } else if (action === 'reset-zoom') {
    charts.forEach((c) =>
      c.dispatchAction({ type: 'dataZoom', start: 0, end: 100 }),
    )
    return
  } else return
  render()
})
selector.addEventListener('change', () => {
  history.pushState(
    null,
    '',
    `?study=${encodeURIComponent(selector.value)}#results`,
  )
  load(selector.value)
})
window.addEventListener('hashchange', render)
window.addEventListener('popstate', () => {
  const id = new URLSearchParams(location.search).get('study') || 'recorded'
  if (id !== active) load(id)
  else render()
})
load(active)
