import { numeric, cell } from './model.js'
export const colors = [
  '#087f72',
  '#b65429',
  '#566bbb',
  '#a54c84',
  '#68802e',
  '#8c62b5',
  '#267f9c',
  '#a44747',
]
export const configurationColorAt = (index) => {
  if (index < colors.length) return colors[index]
  const hue = (index * 137.508) % 360,
    saturation = 0.55,
    lightness = 0.42
  const channel = (offset) => {
    const k = (offset + hue / 30) % 12
    return Math.round(
      255 *
        (lightness -
          saturation *
            Math.min(lightness, 1 - lightness) *
            Math.max(-1, Math.min(k - 3, 9 - k, 1))),
    )
      .toString(16)
      .padStart(2, '0')
  }
  return `#${channel(0)}${channel(8)}${channel(4)}`
}
export function initState(study) {
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
  if (
    study.study_id?.startsWith('infrastructure-') ||
    ['optuna-search', 'optuna-2', 'dispatch-comparison'].includes(
      study.study_id,
    )
  ) {
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
    runColors: Object.fromEntries(
      study.runs.map((r, i) => [r.key, configurationColorAt(i)]),
    ),
    configColors: Object.fromEntries(
      study.configurations.map((c, i) => [c.key, configurationColorAt(i)]),
    ),
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
    signalUnits: {},
    integerColumns: Object.fromEntries(
      study.columns.map((c) => [
        c.id,
        study.runs.every(
          (r) => !numeric(r.values[c.id]) || Number.isInteger(r.values[c.id]),
        ),
      ]),
    ),
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
        .filter(
          (c) =>
            c.kind === 'parameter' && (study.singleRun || c.configurationInput),
        )
        .slice(
          0,
          ['optuna-search', 'optuna-2'].includes(study.study_id) ? 4 : 3,
        )
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
export function inSelectionOrder(items, keys) {
  const byKey = new Map(items.map((item) => [item.key, item]))
  return [...keys].map((key) => byKey.get(key)).filter(Boolean)
}

export function toggle(keys, key, enabled = !keys.has(key)) {
  const next = new Set(keys)
  if (enabled) next.add(key)
  else next.delete(key)
  return next
}
export function move(keys, key, position) {
  const order = [...keys],
    from = order.indexOf(key)
  if (from < 0 || position < 0 || position >= order.length) return keys
  order.splice(from, 1)
  order.splice(position, 0, key)
  return Array.isArray(keys) ? order : new Set(order)
}
export function visibleRows(study, s) {
  const selected = s.mode === 'runs' ? s.runs : s.configs
  const entities = s.mode === 'runs' ? study.runs : study.configurations
  const col = study.columns.find((c) => c.id === s.sort)
  return entities
    .filter(
      (e) =>
        (!s.query ||
          `${e.key} ${e.name} ${e.configuration?.name || ''} ${JSON.stringify(e.runs ? e.values : e.record.parameters)}`
            .toLowerCase()
            .includes(s.query.toLowerCase())) &&
        !(
          s.mode === 'runs' &&
          s.configFilter.length &&
          !s.configFilter.includes(e.configuration.key)
        ),
    )
    .sort((a, b) => {
      const selectedOrder =
        s.selectedFirst &&
        Number(selected.has(b.key)) - Number(selected.has(a.key))
      if (selectedOrder) return selectedOrder
      const av = col ? cell(a, col, s.stat) : a.name,
        bv = col ? cell(b, col, s.stat) : b.name
      if (av == null) return bv == null ? 0 : 1
      if (bv == null) return -1
      const result =
        numeric(av) && numeric(bv)
          ? av - bv
          : String(av).localeCompare(String(bv), undefined, { numeric: true })
      return s.descending ? -result : result
    })
}
