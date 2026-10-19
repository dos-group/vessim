import { unitOptions } from './units.js'

// Public link format. Keep v1 field names stable even if UI state is reorganized.
const choices = {
  mode: ['runs', 'configurations'],
  timeMode: ['runs', 'configurations'],
  plotType: ['distribution', 'scatter', 'ecdf'],
  stat: ['', 'median', 'mean', 'min', 'max'],
  timeStat: ['median', 'mean', 'min', 'max'],
  spread: ['range', 'iqr', 'none'],
  timeSpread: ['range', 'iqr', 'none'],
  alignment: ['elapsed', 'absolute'],
  paretoX: ['min', 'max'],
  paretoY: ['min', 'max'],
}
const booleans = [
  'plot',
  'plotIndividuals',
  'timeIndividuals',
  'pareto',
  'descending',
  'selectedFirst',
]
const arrays = {
  runs: 'runs',
  configs: 'configurations',
  timeConfigs: 'configurations',
  configFilter: 'configurations',
  visible: 'columns',
}
const sets = new Set(['runs', 'configs', 'timeConfigs'])
const strings = ['query', 'x', 'y', 'sort']
const same = (a, b) =>
  JSON.stringify(a instanceof Set ? [...a] : a) ===
  JSON.stringify(b instanceof Set ? [...b] : b)
const object = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
const stringArray = (value) =>
  Array.isArray(value) && value.every((item) => typeof item === 'string')

export function readViewLink(raw, defaults, study) {
  let input
  try {
    input = JSON.parse(raw)
  } catch {
    return defaults
  }
  if (!object(input) || input.v !== 1) return defaults
  const result = { ...defaults }
  for (const [key, options] of Object.entries(choices))
    if (options.includes(input[key])) result[key] = input[key]
  for (const key of booleans)
    if (typeof input[key] === 'boolean') result[key] = input[key]
  for (const key of strings) {
    if (typeof input[key] !== 'string') continue
    if (
      key === 'query' ||
      (key === 'sort' && input[key] === 'name') ||
      study.columns.some((c) => c.id === input[key])
    )
      result[key] = input[key]
  }
  for (const [key, collection] of Object.entries(arrays)) {
    if (!stringArray(input[key])) continue
    const available = new Set(
      study[collection].map((item) => item.id ?? item.key),
    )
    const valid = [...new Set(input[key])].filter((id) => available.has(id))
    // Preserve intentionally empty choices, but fall back if every ID disappeared.
    if (input[key].length && !valid.length) continue
    result[key] = sets.has(key) ? new Set(valid) : valid
  }
  // Signals are validated against recordings once the lazy CSVs have loaded.
  if (stringArray(input.signals)) result.signals = [...new Set(input.signals)]
  for (const key of ['units', 'signalUnits'])
    if (object(input[key]))
      result[key] = Object.fromEntries(
        Object.entries(input[key]).filter(
          ([id, value]) =>
            typeof value === 'string' &&
            (key === 'signalUnits' ||
              study.columns.some(
                (c) =>
                  c.id === id &&
                  (value === 'auto' ||
                    unitOptions(c.unit).some(
                      (option) => option.unit === value,
                    )),
              )),
        ),
      )
  if (
    object(input.zoom) &&
    Number.isFinite(input.zoom.start) &&
    Number.isFinite(input.zoom.end) &&
    input.zoom.start >= 0 &&
    input.zoom.start < input.zoom.end &&
    input.zoom.end <= 100
  )
    result.zoom = { start: input.zoom.start, end: input.zoom.end }
  if (study.singleRun) {
    result.mode = 'runs'
    result.timeMode = 'runs'
    if (result.plotType === 'ecdf') result.plotType = defaults.plotType
  }
  return result
}
export function writeViewLink(href, studyId, page, state, defaults) {
  const url = new URL(href),
    payload = { v: 1 }
  const fields = [
    ...Object.keys(choices),
    ...booleans,
    ...Object.keys(arrays),
    ...strings,
    'signals',
    'units',
    'signalUnits',
    'zoom',
  ]
  for (const key of fields)
    if (!same(state[key], defaults[key]) && state[key] !== undefined)
      payload[key] = state[key] instanceof Set ? [...state[key]] : state[key]
  url.searchParams.set('study', studyId)
  url.searchParams.delete('view')
  if (Object.keys(payload).length > 1)
    url.searchParams.set('view', JSON.stringify(payload))
  url.hash = page
  return url.href
}
