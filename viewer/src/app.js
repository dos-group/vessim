/* global echarts */
import { paretoFront } from './pareto.js'
import { columnNumberFormat, formatNumber } from './numbers.js'
import { summarize, summarizeTrajectories, empiricalDistribution } from './uncertainty.js'
import {
  completedStudy,
  columnGroups,
  metricCategory,
  signalGroups,
  visibleSignals,
  cell,
  sample,
  stable,
  numeric,
  human,
} from './model.js'
import {
  unitOptions,
  displayUnit,
  inDisplayUnit,
} from './units.js'
const main = document.querySelector('#main'),
  selector = document.querySelector('#study')
const studies = new Map(),
  studyIndexes = new Map(),
  catalogStudies = new Map(),
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
const configurationColorAt = (index) => {
  if (index < colors.length) return colors[index]
  const hue = index * 137.508 % 360, saturation = 0.55, lightness = 0.42
  const channel = offset => {
    const k = (offset + hue / 30) % 12
    return Math.round(255 * (lightness - saturation * Math.min(lightness, 1 - lightness) * Math.max(-1, Math.min(k - 3, 9 - k, 1))))
      .toString(16).padStart(2, '0')
  }
  return `#${channel(0)}${channel(8)}${channel(4)}`
}
let active = new URLSearchParams(location.search).get('study') || ''
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
  if (signal.field === 'p_grid') return 'Total grid power'
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
const spec = (c) =>
  displayUnit(c.unit, state().magnitudes[c.id], state().units[c.id])
const unit = (c) => spec(c).unit
const value = (c, v) => (c.kind === 'metric' ? inDisplayUnit(v, spec(c)) : v)
const metricText = (c, v) => {
  const converted = value(c, v)
  return typeof converted === 'number'
    ? formatNumber(converted, columnNumberFormat(
      value(c, state().magnitudes[c.id]),
      c.kind === 'parameter' && state().integerColumns[c.id],
    ))
    : fmt(converted)
}
const scopeLabel = (c) => {
  if (!c.metricPath) return c.scope
  if (!data().singleMicrogrid) return c.metricPath[0] === 'run' ? 'Whole system' : c.scope
  return c.metricPath[0] === 'actors' ? `Actor: ${c.metricPath[2]}`
    : metricCategory(c)
}
const columnLabel = (c) =>
  `${scopeLabel(c)} · ${c.label}${unit(c) && unit(c) !== '1' ? ` (${unit(c)})` : ''}`
const selected = () => state()[state().mode === 'runs' ? 'runs' : 'configs']
const entities = () =>
  state().mode === 'runs' ? data().runs : data().configurations
const configColor = (config) => state().configColors[config.key]
const color = (run) => data().singleRun ? state().runColors[run.key] : configColor(run.configuration)
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
  if (!Array.isArray(state()[kind])) return moveSelection(state()[kind], key, position)
  const order = new Set(state()[kind])
  moveSelection(order, key, position)
  state()[kind] = [...order]
}
function assignRunColors() {
  const s = state()
  // Reserve existing colors before assigning new ones, regardless of order.
  const used = new Set([...s.runs].map((key) => s.runColors[key]).filter(Boolean))
  for (const key of s.runs) {
    if (s.runColors[key]) continue
    s.runColors[key] = colors.find((c) => !used.has(c)) || colors[0]
    used.add(s.runColors[key])
  }
}
function orderControls(entries, kind) {
  if (!entries.length || entries.length > 8) return ''
  const isRun = kind === 'runs'
  return `<section class="selection-order" aria-label="${isRun ? 'Run' : 'Configuration'} order"><ol>${entries.map((e) => `<li data-order-key="${esc(e.key)}" data-kind="${kind}" tabindex="0" aria-label="${esc(e.name)}. Drag or use arrow keys to reorder." aria-keyshortcuts="ArrowLeft ArrowRight" title="Drag to reorder">${isRun ? `<input class="run-color" type="color" data-run-color="${esc(e.key)}" value="${color(e)}" aria-label="Color for ${esc(e.name)}" title="Color for ${esc(e.name)}">` : `<input class="run-color" type="color" data-config-color="${esc(e.key)}" value="${configColor(e)}" aria-label="Color for ${esc(e.name)}">`}<span class="order-name">${esc(e.name)}</span><button data-remove-selection="${esc(e.key)}" data-kind="${kind}" aria-label="Remove ${esc(e.name)}" title="Remove">×</button></li>`).join('')}</ol></section>`
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
    event.target.closest('input') ||
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
  const arrows = ['ArrowLeft', 'ArrowRight']
  if (
    !item ||
    event.target.closest('input') ||
    (item.dataset.kind === 'visible'
      ? !event.altKey
      : event.target.closest('button')) ||
    !arrows.includes(event.key)
  )
    return
  event.preventDefault()
  const keys = state()[item.dataset.kind],
    key = item.dataset.orderKey
  const visibleKeys = [...keys]
  const target = visibleKeys[visibleKeys.indexOf(key) + (event.key === arrows[0] ? -1 : 1)]
  if (!target) return
  reorder(
    item.dataset.kind,
    key,
    [...keys].indexOf(target),
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
  const candidates = varying.length ? varying : metrics
  const defaults = [
    ...candidates.filter((c) => c.scope === 'Run'),
    ...candidates.filter((c) => c.scope !== 'Run'),
  ]
  // Example-specific initial axes; all recorded fields remain selectable.
  if (study.study_id?.startsWith('infrastructure-') || ['optuna-search', 'optuna-2', 'dispatch-comparison'].includes(study.study_id)) {
    const preferred = ['optuna-search', 'optuna-2'].includes(study.study_id)
      ? ['annual cost', 'grid emissions', 'equipment capex']
      : study.study_id === 'dispatch-comparison'
        ? ['electricity cost', 'grid emissions', 'peak grid import']
      : ['initial embodied emissions', 'grid emissions']
    defaults.sort((a, b) => {
      const rank = (c) => {
        const i = preferred.indexOf(c.label)
        return i < 0 ? preferred.length : i
      }
      return rank(a) - rank(b)
    })
  }
  return {
    mode: study.singleRun ? 'runs' : 'configurations',
    runColors: {},
    configColors: Object.fromEntries(study.configurations.map((c, i) => [c.key, configurationColorAt(i)])),
    spread: 'range',
    plotType: study.configurations.length > 12 ? 'scatter' : 'distribution',
    pareto: false,
    paretoX: 'min',
    paretoY: 'min',
    timeMode: study.singleRun ? 'runs' : 'configurations',
    timeConfigs: new Set(),
    timeStat: 'median',
    timeSpread: 'range',
    timeIndividuals: false,
    plotIndividuals: study.runs.length <= 2000,
    plotZoom: [],
    plotZoomKey: '',
    units: {},
    integerColumns: Object.fromEntries(study.columns.map(c => [c.id,
      study.runs.every(r => !numeric(r.values[c.id]) || Number.isInteger(r.values[c.id])),
    ])),
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
    stat: study.singleRun ? '' : 'median',
    x: defaults[0]?.id,
    y: defaults[1]?.id || defaults[0]?.id,
    visible: [
      ...study.columns
        .filter((c) => c.kind === 'parameter' && (study.singleRun || c.configurationInput))
        .slice(0, ['optuna-search', 'optuna-2'].includes(study.study_id) ? 4 : 3)
        .map((c) => c.id),
      ...defaults.slice(0, 3).map((c) => c.id),
    ],
    sort: 'name',
    descending: false,
    selectedFirst: false,
    zoom: { start: 0, end: 100 },
    signals: null,
    closedSignalSites: new Set(),
    alignment: 'elapsed',
    plot: study.runs.length > 1,
    opened: null,
    rowPage: 0,
  }
}
function studyIndex(id) {
  if (!studyIndexes.has(id)) {
    const entry = catalogStudies.get(id)
    if (!entry) throw new Error(`Study unavailable: ${id}`)
    const origin = new URL(entry.url, location.href)
    studyIndexes.set(id, fetch(origin).then(async response => {
      if (!response.ok) throw new Error(`Study unavailable (${response.status})`)
      return { origin, raw: await response.json() }
    }).catch(error => { studyIndexes.delete(id); throw error }))
  }
  return studyIndexes.get(id)
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
    const index = await studyIndex(id),
      raw = structuredClone(index.raw)
    for (const config of raw.configurations) {
      for (const run of config.runs) {
        if (run.trajectoryUrl) run.trajectoryUrl = new URL(run.trajectoryUrl, location.href).href
      }
    }
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
  echarts.disconnect('vessim-time')
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
  if (target === '#scatter') {
    c.on('datazoom', () => { state().plotZoom = c.getOption().dataZoom.map(z => ({start: z.start, end: z.end})) })
  }
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
  document.querySelector('#run-count').textContent = state().timeMode === 'configurations'
    ? data().configurations.filter(c => state().timeConfigs.has(c.key)).reduce((n, c) => n + c.runs.length, 0) : state().runs.size
  if (page() === 'timeseries') renderTimeSeries()
  else if (page().startsWith('run/'))
    renderRun(decodeURIComponent(page().slice(4)))
  else renderResults()
  if (navigated) window.scrollTo(0, 0)
}
function representationControl(trajectory = false) {
  if (data().singleRun) return ''
  const s = state(), mode = trajectory ? s.timeMode : s.mode
  const attr = trajectory ? 'data-time-mode' : 'data-mode'
  const stat = trajectory ? 'timeStat' : 'stat', spread = trajectory ? 'timeSpread' : 'spread'
  const distribution = !trajectory && state().plot && state().plotType === 'ecdf'
  return `<div class="representation" role="group" aria-label="${trajectory ? 'Time series' : 'Results'} display"><span>Show</span><div class="segmented"><button ${attr}="runs" aria-pressed="${mode === 'runs'}">Individual runs</button><button ${attr}="configurations" aria-pressed="${mode === 'configurations'}">Configuration summaries</button></div>${mode === 'configurations' ? `<label>${distribution ? 'Table statistic' : 'Statistic'}<select id="${stat}" aria-label="Statistic">${['median', 'mean', 'min', 'max'].map(v => option(v, human(v), s[stat])).join('')}</select></label>${distribution ? '' : `<label>Spread<select id="${spread}" aria-label="Spread">${option('range', 'Full range', s[spread])}${option('iqr', 'Middle 50%', s[spread])}${option('none', 'None', s[spread])}</select></label><label class="check-label"><input type="checkbox" id="${trajectory ? 'timeIndividuals' : 'plotIndividuals'}" ${s[trajectory ? 'timeIndividuals' : 'plotIndividuals'] ? 'checked' : ''}>Show individual runs</label>`}` : ''}</div>`
}
function header(title) {
  return `<div class="heading"><div><h1>${esc(title)}</h1><p>${esc(data().name)} · ${data().configurations.length} configurations${data().singleRun ? '' : ` · ${data().runs.length} runs`}</p></div></div>`
}
function visibleRows() {
  const s = state()
  const rows = entities().filter((e) => {
    if (
      s.query &&
      !`${e.key} ${e.name} ${e.configuration?.name || ''} ${JSON.stringify(e.runs ? e.values : e.record.parameters)}`
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
  const summary = summarize(values, state().stat, state().spread)
  return `${text}${summary.low !== null && values.length > 1 ? `<small>${metricText(col, summary.low)}–${metricText(col, summary.high)} · ${state().spread === 'iqr' ? 'middle 50%' : 'range'}</small>` : ''}<small>${values.length}/${entity.runs.length} runs</small>`
}
function columnPicker(ids, columns) {
  return `<details class="column-picker"><summary class="button">Columns</summary><div class="picker-options">${columnGroups(columns, data().singleMicrogrid).map(group => `<fieldset class="column-group"><legend>${esc(group.label)}</legend>${group.columns
    .map(
      (c) =>
        `<div class="column-option"><label><input type="checkbox" data-visible="${esc(c.id)}" ${ids.includes(c.id) ? 'checked' : ''}>${esc(c.label)}${unit(c) && unit(c) !== '1' ? ` (${esc(unit(c))})` : ''}</label>${
          ids.includes(c.id) && unitOptions(c.unit).length > 1
            ? `<select data-unit="${esc(c.id)}" aria-label="Display unit for ${esc(scopeLabel(c))} ${esc(c.label)}">${option('auto', `Auto (${displayUnit(c.unit, state().magnitudes[c.id]).unit})`, state().units[c.id] || 'auto')}${unitOptions(
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
function scatterOptions(columns, current) {
  return [['Inputs', columns.filter(c => c.kind === 'parameter')], ['Metrics', columns.filter(c => c.kind === 'metric')]]
    .filter(([, fields]) => fields.length)
    .map(([label, fields]) => `<optgroup label="${label}">${options(fields, current)}</optgroup>`).join('')
}
function paretoControls() {
  const s = state()
  return `<div class="pareto-controls"><label class="check-label"><input id="pareto" type="checkbox" ${s.pareto ? 'checked' : ''}>Pareto front</label>${s.pareto ? `<label>Horizontal objective<select id="paretoX">${option('min', 'Minimize', s.paretoX)}${option('max', 'Maximize', s.paretoX)}</select></label><label>Vertical objective<select id="paretoY">${option('min', 'Minimize', s.paretoY)}${option('max', 'Maximize', s.paretoY)}</select></label>` : ''}</div>`
}
function resultPlotViews() {
  const views = [
    ['distribution', 'By configuration', 'Compare one metric'],
    ['scatter', 'Scatter plot', 'Explore inputs and outcomes'],
    ['ecdf', 'Distribution', data().singleRun ? 'Needs repeated runs' : 'Explore outcome frequencies'],
  ]
  return `<div class="result-views" role="group" aria-label="Results plot view">${views.map(([id, title, description]) => {
    const disabled = id === 'ecdf' && data().singleRun
    return `<button data-plot-view="${id}" aria-pressed="${state().plotType === id}" ${disabled ? 'disabled' : ''}><strong>${title}</strong><span>${description}</span></button>`
  }).join('')}</div>`
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
  const metrics = numericFields.filter(c => c.kind === 'metric')
  if (!numericFields.some(c => c.id === s.x)) s.x = numericFields[0]?.id
  const verticalFields = s.plotType === 'scatter' ? numericFields : metrics
  if (!verticalFields.some(c => c.id === s.y)) s.y = verticalFields[1]?.id || verticalFields[0]?.id
  s.rowPage = Math.min(s.rowPage, Math.max(0, Math.ceil(rows.length / 50) - 1))
  const shown = rows.slice(s.rowPage * 50, (s.rowPage + 1) * 50)
  main.innerHTML = `${header('Results')}${data().description ? `<details class="study-details"><summary>Study details</summary><p>${esc(data().description)}</p></details>` : ''}
  <div class="toolbar"><label class="inline-label">Search<input id="search" type="search" placeholder="Name, ID or parameter" value="${esc(s.query)}"></label><button data-action="plot">${s.plot ? 'Hide' : 'Show'} plot</button></div>
  ${s.configFilter.length && isRun ? `<p class="filter-chip">Runs from ${s.configFilter.length} selected configuration(s) <button data-action="all-runs">Show all runs</button></p>` : ''}
  ${representationControl()}
  ${s.plot ? `<section class="panel plot-panel">${resultPlotViews()}<div class="plot-controls ${['distribution', 'ecdf'].includes(s.plotType) ? 'one-axis' : ''}">${s.plotType === 'scatter' ? `<label>Horizontal axis<select id="x">${scatterOptions(numericFields, s.x)}</select></label>` : ''}<label>${s.plotType === 'scatter' ? 'Vertical axis' : 'Metric'}<select id="y">${s.plotType === 'scatter' ? scatterOptions(verticalFields, s.y) : options(verticalFields, s.y)}</select></label></div><div class="plot-tools">${s.plotType === 'scatter' ? paretoControls() : ''}<button data-action="reset-plot-zoom">Reset zoom</button></div><div id="scatter" class="scatter" aria-label="${s.plotType === 'distribution' ? 'Metric by configuration' : s.plotType === 'ecdf' ? 'Empirical outcome distribution' : 'Scatter plot'}"></div><p id="plot-note" class="plot-note"></p></section>` : ''}
  <div class="selection-toolbar"><span>${selected().size} ${label.toLowerCase()}s selected</span><button data-action="clear" ${!selected().size ? 'disabled' : ''}>Clear</button><button data-action="${isRun ? 'time' : 'config-time'}" ${!selected().size ? 'disabled' : ''}>Time series</button><button data-action="export">Export ${selected().size ? 'selected' : 'filtered'}</button>${columnPicker(s.visible, data().columns)}</div>
  <div class="workspace"><section class="panel"><div class="scroll"><table class="results-table"><thead><tr><th><div class="selection-sort"><input type="checkbox" id="select-page" aria-label="Select visible rows" ${shown.length && shown.every((e) => selected().has(e.key)) ? 'checked' : ''}><button class="selected-first" data-action="selected-first" aria-label="Selected first" title="Selected first" aria-pressed="${s.selectedFirst}"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 13V3m-3 3 3-3 3 3M9 4h6M9 8h4M9 12h2"/></svg></button></div></th><th><button class="sort" data-sort="name">${label} ${s.sort === 'name' ? (s.descending ? '↓' : '↑') : '↕'}</button></th>${isRun ? '' : '<th>Runs</th>'}${columns.map((c) => `<th class="${c.numeric ? 'number' : ''}" data-order-key="${esc(c.id)}" data-kind="visible" title="Drag to reorder; click to sort"><button class="sort" aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight" data-sort="${esc(c.id)}">${esc(c.label)} ${s.sort === c.id ? (s.descending ? '↓' : '↑') : '↕'}</button><small>${esc(scopeLabel(c))}${c.unit ? ` · ${esc(unit(c))}` : ''}</small></th>`).join('')}</tr></thead><tbody>${shown.map((e) => `<tr class="${selected().has(e.key) ? 'selected-row' : ''}"><td><input type="checkbox" data-select="${esc(e.key)}" aria-label="Select ${esc(e.name)}" ${selected().has(e.key) ? 'checked' : ''}></td><td><button class="link" ${isRun ? `data-run="${esc(e.key)}"` : `data-config="${esc(e.key)}"`}>${esc(e.name)}</button>${isRun && !data().singleRun ? `<small>${esc(e.configuration.name)}${e.record.parameters.seed == null ? '' : ` · seed ${esc(e.record.parameters.seed)}`}</small>` : ''}</td>${isRun ? '' : `<td>${count(e)}</td>`}${columns.map((c) => `<td class="${c.numeric ? 'number' : ''}">${displayCell(e, c)}</td>`).join('')}</tr>${!isRun && s.opened === e.key ? `<tr class="expanded-config"><td colspan="${columns.length + 3}">${configDetail(e)}</td></tr>` : ''}`).join('')}</tbody></table>${!rows.length ? '<p class="empty">No matching completed results.</p>' : ''}</div><div class="table-footer">${rows.length} matching ${label.toLowerCase()}s<span><button data-action="prev" ${s.rowPage === 0 ? 'disabled' : ''}>←</button> ${s.rowPage + 1} / ${Math.max(1, Math.ceil(rows.length / 50))} <button data-action="next" ${(s.rowPage + 1) * 50 >= rows.length ? 'disabled' : ''}>→</button></span></div></section></div>`
  if (s.plot) {
    if (s.plotType === 'distribution') renderDistribution(rows)
    else if (s.plotType === 'ecdf') renderOutcomeDistribution(rows)
    else renderScatter(rows)
  }
}
function resultZoom() {
  const s = state(), key = `${s.plotType}/${s.x}/${s.y}`
  if (s.plotZoomKey !== key) { s.plotZoom = []; s.plotZoomKey = key }
  const axes = s.plotType === 'distribution' ? [{yAxisIndex: 0}] : s.plotType === 'ecdf' ? [{xAxisIndex: 0}] : [{xAxisIndex: 0}, {yAxisIndex: 0}]
  return axes.map((axis, i) => ({type: 'inside', ...axis, filterMode: 'none', start: 0, end: 100, ...s.plotZoom[i]}))
}
function plotOverview(points, limit = 10000) {
  if (points.length <= limit) return points
  const stride = points.length / limit
  return Array.from({length: limit}, (_, i) => points[Math.floor(i * stride)])
}
function renderDistribution(rows) {
  const s = state(), metric = field(s.y), summaryMode = s.mode === 'configurations'
  if (!metric) { document.querySelector('#plot-note').textContent = 'No numeric metrics recorded.'; return }
  const configurations = summaryMode ? rows : [...new Set(rows.map(r => r.configuration))]
  const shown = configurations.slice(0, 50), dots = [], centers = [], ranges = []
  let excluded = 0
  shown.forEach((config, i) => {
    const sampled = sample(config, metric)
    const runs = summaryMode ? sampled.points.map(p => p.run) : rows.filter(r => r.configuration === config)
    if (summaryMode && sampled.reason) { excluded += config.runs.length; return }
    const valid = runs.filter(r => numeric(cell(r, metric)))
    excluded += (summaryMode ? config.runs.length : runs.length) - valid.length
    const values = valid.map(r => value(metric, cell(r, metric)))
    valid.forEach((run, j) => dots.push({
      key: summaryMode ? config.key : run.key,
      name: `${config.name}\n${run.key}${run.record.parameters.seed == null ? '' : ` · seed ${run.record.parameters.seed}`}\n${fmt(values[j])} ${unit(metric)}`,
      value: [i, values[j]],
      symbolOffset: [(j - (valid.length - 1) / 2) * Math.min(7, 36 / Math.max(1, valid.length - 1)), 0],
      symbolSize: !summaryMode && s.runs.has(run.key) ? 11 : 7,
      itemStyle: {color: configColor(config), opacity: summaryMode ? 0.25 : 0.85},
    }))
    if (summaryMode && values.length) {
      const stats = summarize(values, s.stat, s.spread)
      centers.push({key: config.key, value: [i, stats.center], symbolSize: s.configs.has(config.key) ? 17 : 12,
        name: `${config.name}\n${human(s.stat)}: ${fmt(stats.center)} ${unit(metric)}\n${stats.count}/${config.runs.length} runs`, itemStyle: {color: configColor(config)}})
      if (stats.low !== null) ranges.push({value: [i, stats.low, stats.high], itemStyle: {color: configColor(config)}})
    }
  })
  chart('#scatter', {
    tooltip: {trigger: 'item', renderMode: 'richText', confine: true, formatter: p => p.name},
    dataZoom: resultZoom(),
    grid: {left: 85, right: 35, top: 28, bottom: 65},
    xAxis: {type: 'category', data: shown.map(c => c.name), boundaryGap: true,
      axisLabel: {hideOverlap: true}, splitLine: {show: false}},
    yAxis: {type: 'value', name: `${metric.label}${unit(metric) ? ` (${unit(metric)})` : ''}`, scale: true, splitLine: {lineStyle: {color: '#e4e9e6'}}},
    series: [
      {type: 'custom', silent: true, clip: true, encode: {x: 0, y: [1, 2]}, data: ranges, renderItem: (params, api) => {
        const a = api.coord([api.value(0), api.value(1)]), b = api.coord([api.value(0), api.value(2)])
        const style = {stroke: api.visual('color'), lineWidth: 2}
        return {type: 'group', children: [
          {type: 'line', shape: {x1: a[0], y1: a[1], x2: b[0], y2: b[1]}, style},
          ...[a, b].map(p => ({type: 'line', shape: {x1: p[0] - 5, y1: p[1], x2: p[0] + 5, y2: p[1]}, style})),
        ]}
      }},
      {name: 'Individual runs', type: 'scatter', data: summaryMode && !s.plotIndividuals ? [] : plotOverview(dots), z: 3},
      {name: human(s.stat), type: 'scatter', symbol: 'diamond', data: centers, z: 4},
    ],
  }, event => {
    const key = event.data?.key
    if (key) { if (selected().has(key)) selected().delete(key); else selected().add(key); render() }
  })
  const definitions = new Set(shown.flatMap(c => c.runs.filter(r => numeric(r.values[metric.id])).map(r => stable([r.definitions[metric.id], r.record.execution.simulated_duration]))))
  document.querySelector('#plot-note').textContent = `${summaryMode ? `${human(s.stat)} markers${s.spread === 'none' ? '' : s.spread === 'iqr' ? ' and middle 50% ranges' : ' and observed ranges'}${s.plotIndividuals ? '; faint dots are individual runs' : ''}.` : 'Each dot is one run; colors identify configurations.'} ${excluded ? `${excluded} values missing or incompatible. ` : ''}${configurations.length > shown.length ? `Showing the first ${shown.length} of ${configurations.length} configurations; filter to narrow the plot.` : ''}${definitions.size > 1 ? ' Metric definitions or durations differ; inspect recorded assumptions before comparison.' : ''}`
  if (dots.length > 10000 && (!summaryMode || s.plotIndividuals))
    document.querySelector('#plot-note').textContent += ` Showing 10,000 of ${dots.length.toLocaleString()} run points. Summaries use all runs.`
}

function renderOutcomeDistribution(rows) {
  const s = state(), metric = field(s.y), note = document.querySelector('#plot-note')
  if (!metric) {
    note.textContent = 'No numeric metrics recorded.'
    return
  }
  const configurations = s.mode === 'configurations' ? rows : [...new Set(rows.map(r => r.configuration))]
  const shown = configurations.slice(0, 12), curves = []
  let excluded = 0
  for (const config of shown) {
    const runs = s.mode === 'configurations' ? config.runs : rows.filter(r => r.configuration === config)
    const sampled = sample({...config, runs}, metric)
    if (sampled.reason) {
      excluded += runs.length
      continue
    }
    excluded += runs.length - sampled.points.length
    const values = sampled.points.map(p => value(metric, p.value))
    const points = empiricalDistribution(values)
    if (points.length) curves.push({config, points, count: values.length})
  }
  if (!curves.length) {
    document.querySelector('#scatter').innerHTML = '<p class="empty">No comparable recorded values for this metric. Try another metric or configuration.</p>'
    note.textContent = `${excluded} values missing or incompatible.`
    return
  }
  const low = Math.min(...curves.map(c => c.points[0][0]))
  const high = Math.max(...curves.map(c => c.points.at(-1)[0]))
  chart('#scatter', {
    tooltip: {trigger: 'item', renderMode: 'richText', confine: true, formatter: p => p.name},
    legend: {type: 'scroll', top: 0, left: 0, right: 0},
    dataZoom: resultZoom(),
    grid: {left: 85, right: 35, top: 55, bottom: 65},
    xAxis: {type: 'value', name: `${metric.label}${unit(metric) ? ` (${unit(metric)})` : ''}`,
      nameLocation: 'middle', nameGap: 38, scale: true, splitLine: {show: false}},
    yAxis: {type: 'value', min: 0, max: 100, name: 'Runs at or below (%)',
      axisLabel: {formatter: '{value}%'}, splitLine: {lineStyle: {color: '#e4e9e6'}}},
    series: curves.map(({config, points, count}) => ({
      name: `${config.name} (n=${count})`, type: 'line', step: 'end', showSymbol: true, symbolSize: 6,
      lineStyle: {width: 2, color: configColor(config)}, itemStyle: {color: configColor(config)},
      data: [[low, 0], ...points, [high, 100]].map(([x, y]) => ({
        value: [x, y], name: `${config.name}\n${fmt(y)}% of ${count} runs at or below ${fmt(x)} ${unit(metric)}`,
      })),
    })),
  })
  const signatures = new Set(shown.flatMap(c => c.runs.filter(r => numeric(r.values[metric.id]))
    .map(r => stable([r.definitions[metric.id], r.record.execution.simulated_duration]))))
  note.textContent = 'Each step shows the share of recorded runs at or below a metric value. Curves use individual outcomes, with no fitted distribution.'
  if (excluded) note.textContent += ` ${excluded} values missing or incompatible.`
  if (configurations.length > shown.length) note.textContent += ` Showing the first ${shown.length} configurations. Filter the results to narrow the plot.`
  if (signatures.size > 1) note.textContent += ' Metric definitions or durations differ. Inspect recorded assumptions before comparison.'
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
      paint: data().singleRun ? undefined : configColor(e.runs ? e : e.configuration),
      value: [value(x, cell(e, x, s.stat)), value(y, cell(e, y, s.stat))],
    }))
    .filter((p) => p.value.every(numeric))
  note.textContent = `${points.length} points · ${rows.length - points.length} omitted for missing or incompatible values. Click a point to select it; use the table to open details.${s.mode === 'configurations' ? ` ${human(s.stat)} of completed runs; counts are shown in the table.${s.plotIndividuals ? ' Faint points show individual runs.' : ''}` : ''}`
  if ([x, y].some(c => c.kind === 'parameter'))
    note.textContent += ' Other inputs may vary between configurations. Points show recorded outcomes, not an isolated causal effect.'
  const pointKeys = new Set(points.map(p => p.key))
  const comparedRuns = rows.filter(e => pointKeys.has(e.key)).flatMap(e => e.runs || [e])
  const definitionsVary = [x, y].some(
    (c) =>
      c.kind === 'metric' &&
      new Set(
        comparedRuns.filter((r) => numeric(r.values[c.id]))
          .map((r) => stable([r.definitions[c.id], r.record.execution.simulated_duration])),
      ).size > 1,
  )
  if (definitionsVary)
    note.textContent +=
      ' Recorded metric definitions or durations differ. Review assumptions in run details.'
  const front = s.pareto && !definitionsVary ? paretoFront(points, s.paretoX, s.paretoY) : []
  if (s.pareto) {
    if (definitionsVary) note.textContent += ' Pareto front unavailable for incompatible results.'
    else note.textContent += ` Pareto front: ${front.length} nondominated ${s.mode === 'configurations' ? `${s.stat} summaries` : 'runs'} among the filtered points. Horizontal: ${s.paretoX === 'min' ? 'minimize' : 'maximize'}. Vertical: ${s.paretoY === 'min' ? 'minimize' : 'maximize'}.`
  }
  const individualCount = s.mode === 'configurations' && s.plotIndividuals
    ? rows.reduce((count, config) => count + config.runs.length, 0) : points.length
  if (individualCount > 10000)
    note.textContent += ` Showing a 10,000-point overview of ${individualCount.toLocaleString()} runs. Summaries and the Pareto front use all filtered results.`
  chart(
    '#scatter',
    {
      tooltip: { trigger: 'item', renderMode: 'richText', confine: true },
      dataZoom: resultZoom(),
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
          data: plotOverview(points).map((p) => ({
            ...p,
            symbolSize: selected().has(p.key) ? 12 : 8,
            itemStyle: {
              color: data().singleRun ? (selected().has(p.key) ? '#b65429' : '#087f72') : p.paint,
              opacity: 0.8,
            },
          })),
        },
        ...(s.mode === 'configurations' && s.plotIndividuals ? [{
          name: 'Individual runs', type: 'scatter', z: 1, symbolSize: 6,
          data: plotOverview(rows.flatMap(config => config.runs.map(run => ({
            key: config.key,
            name: `${config.name} · ${run.key}${run.record.parameters.seed == null ? '' : ` · seed ${run.record.parameters.seed}`}`,
            value: [value(x, cell(run, x)), value(y, cell(run, y))],
            itemStyle: {color: configColor(config), opacity: 0.2},
          }))).filter(p => p.value.every(numeric))),
        }] : []),
        ...(front.length ? [{
          name: 'Pareto front', type: 'line', z: 5, showSymbol: true, symbol: 'emptyCircle', symbolSize: 12,
          lineStyle: {color: '#263f38', width: 1.5, type: 'dashed'},
          itemStyle: {color: '#263f38', borderWidth: 2},
          data: front,
        }] : []),
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
    c.values,
  )
    .map(([k, v]) => `<dt>${esc(field(k)?.label || k)}</dt><dd>${esc(fmt(v))}</dd>`)
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
  const singleRun = run.configuration.runs.length === 1
  const groups = columnGroups(data().columns.filter((c) => c.id in run.values), data().singleMicrogrid)
  main.innerHTML = `<p class="breadcrumb"><a href="#results">${esc(data().name)}</a> / ${singleRun ? esc(run.configuration.name) : `<button class="link" data-drill="${esc(run.configuration.key)}">${esc(run.configuration.name)}</button> / ${esc(key)}`}</p><div class="heading"><div><h1>${esc(singleRun ? run.configuration.name : key)}</h1><p>${singleRun ? `Run ${esc(key)}` : `Configuration: ${esc(run.configuration.name)}`}${run.realization?.id ? ` · ${esc(run.realization.id)}` : ''}</p></div><button data-add-time="${esc(key)}">${run.trajectoryUrl ? 'Add to time series' : 'Inspect recording availability'}</button></div>
  <section class="panel scroll"><table class="inspector-table"><thead><tr><th scope="col">Parameter / metric</th><th scope="col">Recorded value</th><th scope="col">Description & assumptions</th></tr></thead>${groups.map((group) => `<tbody><tr class="inspector-group"><th colspan="3" scope="rowgroup">${esc(group.label)}</th></tr>${group.columns.map((c) => {
    const definition = run.definitions[c.id]
    const assumptions = definition?.assumptions
    const hasAssumptions = assumptions != null && Object.keys(assumptions).length > 0
    return `<tr><th scope="row">${esc(c.label)}</th><td class="number">${esc(metricText(c, run.values[c.id]))}${unit(c) && unit(c) !== '1' ? ` ${esc(unit(c))}` : ''}</td><td>${esc(definition?.description || '')}${hasAssumptions ? `<details><summary>Assumptions</summary><pre>${esc(JSON.stringify(assumptions, null, 2))}</pre></details>` : ''}</td></tr>`
  }).join('')}</tbody>`).join('')}</table></section><details><summary>Configuration and execution</summary><pre>${esc(JSON.stringify({ parameters: run.record.parameters, config: run.record.config, execution: run.record.execution }, null, 2))}</pre></details>`
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
    new URL('./recording.worker.js', import.meta.url),
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
function signalPicker(groups, chosen) {
  const single = data().singleMicrogrid && groups.length === 1
  return groups.map(({ site, groups }) => {
    const contents = groups.map((group) => `<fieldset class="column-group"><legend>${esc(group.label)}</legend>${group.signals.map((sig) => `<label><input type="checkbox" data-signal="${esc(sig.id)}" aria-label="${single ? '' : `${esc(sig.grid)} · `}${esc(signalLabel(sig))} (${esc(sig.unit)})" ${chosen.includes(sig.id) ? 'checked' : ''}>${esc(signalLabel(sig))} (${esc(sig.unit)})</label>`).join('')}</fieldset>`).join('')
    return single ? contents : `<details class="signal-site" data-signal-site="${esc(site)}" ${state().closedSignalSites.has(site) ? '' : 'open'}><summary>Microgrid · ${esc(site)}</summary>${contents}</details>`
  }).join('')
}
function trajectorySeries(supported) {
  const s = state(), aggregate = !data().singleRun && s.timeMode === 'configurations'
  const line = (run, sig, faint = false) => ({
    id: run.key, name: `${run.name}${run.record.parameters.seed == null ? '' : ` · seed ${run.record.parameters.seed}`}`,
    type: 'line', step: 'end', showSymbol: false, connectNulls: false,
    lineStyle: {width: faint ? 1 : 1.6, color: color(run), opacity: faint ? 0.25 : 0.8},
    itemStyle: {color: color(run)},
    data: sig.points.map(([t, v]) => [s.alignment === 'elapsed' ? (t - time(run.record.config.environment?.sim_start)) / 3600000 : t, v]),
  })
  if (!aggregate) return {series: supported.map(({run, signal}) => line(run, signal)), notes: []}
  const series = [], notes = []
  for (const config of inSelectionOrder(data().configurations, s.timeConfigs)) {
    const matches = supported.filter(m => m.run.configuration === config)
    if (!matches.length) continue
    try {
      const points = summarizeTrajectories(matches.map(({run, signal}) => ({
        count: signal.count, points: line(run, signal).data,
      })), s.timeStat, s.timeSpread)
      const counts = points.map(p => p.count), min = Math.min(...counts), max = Math.max(...counts)
      notes.push(`${config.name}: ${min === max ? min : `${min}–${max}`}/${config.runs.length} runs per timestamp`)
      const paint = configColor(config)
      if (s.timeSpread !== 'none') series.push({
        id: `band-${config.key}`, name: `${config.name} spread`, type: 'custom', silent: true, z: 1, encode: {x: [0, 3], y: [1, 2]},
        data: points.slice(0, -1).flatMap((p, i) => p.low === null || points[i + 1].low === null ? [] : [[p.time, p.low, p.high, points[i + 1].time]]),
        renderItem: (params, api) => {
          const coords = [[api.value(0), api.value(1)], [api.value(3), api.value(1)], [api.value(3), api.value(2)], [api.value(0), api.value(2)]].map(p => api.coord(p))
          return {type: 'polygon', shape: {points: echarts.graphic.clipPointsByRect(coords, params.coordSys)}, style: {fill: paint, opacity: 0.16}}
        },
      })
      if (s.timeIndividuals) series.push(...matches.map(({run, signal}) => line(run, signal, true)))
      series.push({id: `summary-${config.key}`, name: `${config.name} · ${human(s.timeStat)}`, type: 'line', step: 'end', showSymbol: false,
        connectNulls: false, z: 4, lineStyle: {width: 2.2, color: paint}, itemStyle: {color: paint},
        data: points.map(p => ({value: [p.time, p.center], name: `${p.count}/${config.runs.length} runs`})),
      })
    } catch (error) { notes.push(`${config.name}: ${error.message}`) }
  }
  return {series, notes}
}

function renderTimeSeries() {
  const s = state(), aggregate = !data().singleRun && s.timeMode === 'configurations'
  const chosenConfigs = inSelectionOrder(data().configurations, s.timeConfigs)
  const runs = aggregate ? chosenConfigs.flatMap(c => c.runs) : inSelectionOrder(data().runs, s.runs)
  const pool = aggregate ? data().configurations : s.configs.size
    ? data().runs.filter(r => s.configs.has(r.configuration.key)) : data().runs
  const label = aggregate ? 'configurations' : 'runs', entries = aggregate ? chosenConfigs : runs
  main.innerHTML = `<div class="heading"><div><h1>Time series</h1><p>${esc(data().name)} · ${entries.length} selected ${entries.length === 1 ? label.slice(0, -1) : label}</p></div><a class="button" href="#results">Back to results</a></div>
  ${representationControl(true)}<div class="toolbar"><details class="column-picker"><summary class="button">Choose ${label} (${entries.length})</summary><div class="picker-options">${pool.map(r => `<label><input type="checkbox" ${aggregate ? 'data-time-config' : 'data-time-run'}="${esc(r.key)}" ${(aggregate ? s.timeConfigs : s.runs).has(r.key) ? 'checked' : ''}>${esc(aggregate ? r.name : r.key)}${aggregate ? ` · ${r.runs.length} runs` : !r.trajectoryUrl ? ' · no recording' : ''}</label>`).join('')}</div></details><label class="inline-label">Time alignment<select id="alignment">${option('elapsed', 'Elapsed from simulation start (h)', s.alignment)}${option('absolute', 'Recorded time (UTC)', s.alignment)}</select></label><button data-action="reset-zoom">Reset zoom</button><button data-action="clear-runs" ${!entries.length ? 'disabled' : ''}>Clear ${label}</button></div>`
  main.innerHTML += orderControls(entries, aggregate ? 'timeConfigs' : 'runs')
  if (!aggregate && !data().singleRun && runs.length > 8) main.innerHTML += `<div class="configuration-legend">${[...new Set(runs.map(r => r.configuration))].map(c => `<label><input type="color" class="run-color" data-config-color="${esc(c.key)}" value="${configColor(c)}" aria-label="Color for ${esc(c.name)}">${esc(c.name)}</label>`).join('')}</div>`
  if (!runs.length) {
    main.innerHTML += `<p class="empty">Choose ${label} to plot recorded trajectories.</p>`
    return
  }
  if (runs.length > (aggregate ? 100 : data().singleRun ? 8 : 50) || (aggregate && chosenConfigs.length > 8)) {
    main.innerHTML += `<p class="empty">Choose ${aggregate ? 'up to eight configurations and 100 recorded runs' : data().singleRun ? 'up to eight runs' : 'up to 50 runs'} for readable overlays.</p>`
    return
  }
  if (aggregate) main.innerHTML += `<p class="note">${human(s.timeStat)} at each matching timestamp${s.timeSpread === 'none' ? '' : s.timeSpread === 'iqr' ? ' with the middle 50% of recorded values' : ' with the observed min–max range'}. Summaries use all available runs in each selected configuration; bands are not confidence intervals.</p>`
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
  const rank = (sig) => sig.gridPower ? 0 : sig.field === 'p_delta' ? 1
    : sig.field.startsWith('dispatch_states.') ? 2 : 3
  const available = visibleSignals([...signals.values()], loaded.map(r => ({config: r.record.config, series: recording(r).series}))).sort((a, b) =>
    a.grid.localeCompare(b.grid) || rank(a) - rank(b) ||
    signalLabel(a).localeCompare(signalLabel(b), undefined, { numeric: true }) || a.id.localeCompare(b.id))
  const groups = signalGroups(available)
  if (s.signals === null)
    s.signals = available
      .filter((sig) => sig.gridPower || (data().singleMicrogrid && sig.field.endsWith('.soc')))
      .slice(0, 3)
      .map((sig) => sig.id)
  const chosen = groups.flatMap(({ groups }) => groups.flatMap(group => group.signals))
    .filter(sig => s.signals.includes(sig.id))
    .map(sig => sig.id)
  main.innerHTML += `<div class="toolbar"><details class="column-picker"><summary class="button">Signals (${chosen.length})</summary><div class="picker-options">${signalPicker(groups, chosen)}</div></details><details class="column-picker"><summary class="button">Download CSV</summary><div class="picker-options">${loaded.map((r) => `<a href="${esc(r.trajectoryUrl)}" download>${esc(r.key)}</a>`).join('')}</div></details></div>`
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
    const prepared = error ? {series: [], notes: []} : trajectorySeries(supported)
    main.innerHTML += `<section class="panel trajectory-panel" data-signal-panel="${esc(id)}"><div class="chart-heading"><h2>${esc(signalLabel(signal))}</h2><span>${data().singleMicrogrid ? '' : `${esc(signal.grid)} · `}${esc(unit)}</span><button class="remove-signal" data-remove-signal="${esc(id)}" aria-label="Remove ${esc(signalLabel(signal))} chart" title="Remove chart">×</button></div>${missing.length ? `<p class="note">Signal missing in: ${esc(missing.join(', '))}</p>` : ''}${prepared.notes.length ? `<p class="note">${prepared.notes.map(esc).join(' · ')}</p>` : ''}${error ? `<p class="notice">${error}</p>` : `<div id="signal-${i}" class="time-chart" aria-label="${esc(signal.field)} trajectory chart"></div>`}</section>`
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
              axisLabel: { hideOverlap: true, showMinLabel: false, showMaxLabel: false },
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
            series: prepared.series,
          },
          null,
          'vessim-time',
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
  echarts.connect('vessim-time')
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
    let t = typeof v === 'number' ? String(v) : fmt(v)
    if (v == null) t = ''
    if (typeof v !== 'number' && /^[=+\-@\t\r]/.test(t)) t = "'" + t
    return '"' + t.replaceAll('"', '""') + '"'
  }
  const aggregated = state().mode === 'configurations'
  const exportColumns = cols.flatMap(c => {
    const columns = [{label: columnLabel(c), read: e => value(c, cell(e, c, state().stat))}]
    if (aggregated && c.kind === 'metric') {
      const stats = e => summarize(sample(e, c).points.map(p => value(c, p.value)), state().stat, state().spread)
      if (state().spread !== 'none') columns.push(
        {label: `${columnLabel(c)} · ${state().spread === 'iqr' ? 'Q25' : 'min'}`, read: e => stats(e).low},
        {label: `${columnLabel(c)} · ${state().spread === 'iqr' ? 'Q75' : 'max'}`, read: e => stats(e).high},
      )
      columns.push({label: `${columnLabel(c)} · contributing runs`, read: e => stats(e).count})
    }
    return columns
  })
  const lines = [
    ['id', 'configuration', 'summary', ...exportColumns.map(c => c.label)],
    ...rows.map(e => [e.key, e.runs ? e.key : e.configuration.key,
      e.runs ? state().stat : 'recorded', ...exportColumns.map(c => c.read(e))]),
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
    label = oldPicker.querySelector('summary').textContent.split('(')[0],
    scroll = oldPicker.querySelector('.picker-options').scrollTop,
    attribute = input.hasAttribute('data-unit') ? 'data-unit'
      : input.hasAttribute('data-signal') ? 'data-signal' : 'data-visible',
    key = input.getAttribute(attribute)
  render()
  const picker = [...main.querySelectorAll('.column-picker')].find(
    (p) => p.querySelector('summary').textContent.split('(')[0] === label,
  )
  if (!picker) return
  picker.open = true
  ;[...picker.querySelectorAll(`[${attribute}]`)]
    .find((control) => control.getAttribute(attribute) === key)
    ?.focus({ preventScroll: true })
  picker.querySelector('.picker-options').scrollTop = scroll
}
main.addEventListener('toggle', (event) => {
  const site = event.target.dataset.signalSite
  if (site == null || !main.contains(event.target) || !state()) return
  if (event.target.open) state().closedSignalSites.delete(site)
  else state().closedSignalSites.add(site)
}, true)
main.addEventListener('change', (event) => {
  const e = event.target,
    s = state()
  if (e.dataset.configColor) { s.configColors[e.dataset.configColor] = e.value; render(); return }
  if (e.dataset.runColor) {
    if (data().singleRun) s.runColors[e.dataset.runColor] = e.value
    else s.configColors[data().runs.find(r => r.key === e.dataset.runColor).configuration.key] = e.value
    render()
    ;[...main.querySelectorAll('[data-run-color]')]
      .find((input) => input.dataset.runColor === e.dataset.runColor)?.focus({ preventScroll: true })
    return
  }
  if (e.dataset.unit) {
    s.units[e.dataset.unit] = e.value
    refreshPicker(e)
    return
  }
  if (['x', 'y', 'paretoX', 'paretoY', 'stat', 'spread', 'timeStat', 'timeSpread', 'alignment'].includes(e.id)) {
    s[e.id] = e.value
    s.rowPage = 0
  } else if (['timeIndividuals', 'plotIndividuals', 'pareto'].includes(e.id)) {
    s[e.id] = e.checked
  } else if (e.dataset.timeConfig) {
    if (e.checked) s.timeConfigs.add(e.dataset.timeConfig)
    else s.timeConfigs.delete(e.dataset.timeConfig)
    refreshPicker(e)
    return
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
    refreshPicker(e)
    return
  } else return
  render()
  if (e.dataset.timeRun)
    document.querySelector('.column-picker')?.setAttribute('open', '')
})
main.addEventListener('click', (event) => {
  const e = event.target.closest('button')
  if (!e) return
  const s = state(),
    action = e.dataset.action
  if (e.dataset.plotView) {
    s.plotType = e.dataset.plotView
    render()
    main.querySelector(`[data-plot-view="${s.plotType}"]`)?.focus({ preventScroll: true })
    return
  }
  if (e.dataset.removeSignal) {
    s.signals = s.signals.filter((id) => id !== e.dataset.removeSignal)
    render()
    return
  }
  if (e.dataset.removeSelection) {
    s[e.dataset.kind].delete(e.dataset.removeSelection)
    render()
    main.querySelector('[data-order-key]')?.focus()
    return
  }
  if (e.dataset.timeMode) {
    if (e.dataset.timeMode === 'runs') s.runs = new Set(inSelectionOrder(data().configurations, s.timeConfigs).flatMap(c => c.runs.map(r => r.key)))
    else s.timeConfigs = new Set(inSelectionOrder(data().runs, s.runs).map(r => r.configuration.key))
    s.timeMode = e.dataset.timeMode
    render()
    return
  }
  if (e.dataset.mode) {
    if (e.dataset.mode === 'runs') s.runs = new Set(inSelectionOrder(data().configurations, s.configs).flatMap(c => c.runs.map(r => r.key)))
    else s.configs = new Set(inSelectionOrder(data().runs, s.runs).map(r => r.configuration.key))
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
    s.opened = s.opened === e.dataset.config ? null : e.dataset.config
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
    s.timeMode = 'runs'
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
  else if (action === 'clear-runs') { if (s.timeMode === 'configurations') s.timeConfigs.clear(); else s.runs.clear() }
  else if (action === 'close') s.opened = null
  else if (action === 'reset-plot-zoom') s.plotZoom = []
  else if (action === 'plot') s.plot = !s.plot
  else if (action === 'prev') s.rowPage = Math.max(0, s.rowPage - 1)
  else if (action === 'next') s.rowPage++
  else if (action === 'all-runs') s.configFilter = []
  else if (action === 'all-picker-runs') s.configs.clear()
  else if (action === 'config-time') {
    s.timeConfigs = new Set(s.configs)
    s.timeMode = 'configurations'
    route('timeseries')
    return
  } else if (action === 'time') {
    s.timeMode = 'runs'
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
document.querySelector('#timeseries-nav').addEventListener('click', () => {
  if (state() && page() === 'results' && state().mode === 'configurations' && state().configs.size) {
    state().timeConfigs = new Set(state().configs)
    state().timeMode = 'configurations'
  } else if (state() && page() === 'results' && state().mode === 'runs' && state().runs.size) state().timeMode = 'runs'
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
  const id = new URLSearchParams(location.search).get('study') || catalogStudies.keys().next().value
  if (id !== active) load(id)
  else render()
})
async function initialize() {
  try {
    const response = await fetch(new URL('catalog.json', location.href))
    if (!response.ok) throw new Error(`Catalog unavailable (${response.status})`)
    const catalog = await response.json()
    if (!Array.isArray(catalog.studies)) throw new Error('Invalid viewer catalog')
    for (const entry of catalog.studies) catalogStudies.set(entry.study_id, entry)
    selector.replaceChildren(...catalog.studies.map(entry => {
      const item = document.createElement('option')
      item.value = entry.study_id
      item.textContent = entry.name
      return item
    }))
    if (!catalog.studies.length) {
      main.innerHTML = `<h1>No studies available</h1><p>Open an experiment, a study.json file, or a directory of recorded experiments with vessim view.</p>${issues(catalog.errors)}`
      return
    }
    selector.disabled = false
    const notice = document.querySelector('#catalog-notice')
    notice.innerHTML = issues(catalog.errors)
    if (!active) active = catalog.studies[0].study_id
    await load(active)
  } catch (error) {
    main.innerHTML = `<h1>Could not open results</h1><p>${esc(error.message)}</p><p>Start the viewer with vessim view &lt;path&gt;, or serve an exported report over HTTP.</p>`
  }
}
function issues(errors = []) {
  return errors.length ? `<details class="data-issues"><summary>${errors.length} data issue${errors.length === 1 ? '' : 's'}</summary><ul>${errors.map(error => `<li>${esc(error)}</li>`).join('')}</ul></details>` : ''
}
initialize()
