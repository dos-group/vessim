// Shared, DOM-free analysis helpers for the viewer.
export const numeric = (v) => typeof v === 'number' && Number.isFinite(v)
export const stable = (v) =>
  JSON.stringify(
    v && typeof v === 'object' && !Array.isArray(v)
      ? Object.fromEntries(
          Object.keys(v)
            .sort()
            .map((k) => [k, JSON.parse(stable(v[k]))]),
        )
      : (v ?? null),
  )
export const human = (s) => s.replaceAll('_', ' ')
export function completedStudy(raw) {
  const configurations = raw.configurations
    .map((c) => ({
      ...c,
      runs: c.runs.filter((r) => r.record.execution.status === 'completed'),
    }))
    .filter((c) => c.runs.length)
  const study = indexStudy({ ...raw, configurations })
  study.singleRun =
    configurations.length > 0 &&
    configurations.every((c) => c.runs.length === 1)
  if (study.singleRun)
    study.runs.forEach((r) => {
      r.name = r.configuration.name
    })
  return study
}
export function flatten(value, prefix = [], output = {}) {
  for (const [key, child] of Object.entries(value ?? {})) {
    const path = [...prefix, key]
    if (child && typeof child === 'object' && !Array.isArray(child))
      flatten(child, path, output)
    else output[JSON.stringify(path)] = child
  }
  return output
}
export function indexStudy(study) {
  const columns = new Map()
  const parameter = (path, value, configurationInput = false) => {
    const id = `p:${path}`,
      prior = columns.get(id)
    columns.set(id, {
      id,
      kind: 'parameter',
      parameterPath: JSON.parse(path),
      configurationInput:
        configurationInput || prior?.configurationInput || false,
      label: JSON.parse(path).map(human).join(' / '),
      scope: 'Parameter',
      unit: '',
      numeric: numeric(value) || prior?.numeric,
    })
    return id
  }
  const runParameters = new Set(study.run_parameters || [])
  const configurations = study.configurations.map((c) => {
    const inputs = c.runs.map((r) => flatten(r.record.parameters))
    // Membership is explicit in the index. Only displayed shared values are derived.
    const shared = Object.entries(inputs[0] || {}).filter(
      ([path, value]) =>
        !runParameters.has(JSON.parse(path)[0]) &&
        inputs.every(
          (input) =>
            Object.hasOwn(input, path) && stable(input[path]) === stable(value),
        ),
    )
    return {
      ...c,
      name: c.name || c.configuration_id,
      key: c.configuration_id,
      values: Object.fromEntries(
        shared.map(([p, v]) => [parameter(p, v, true), v]),
      ),
    }
  })
  const runs = configurations.flatMap((c) =>
    c.runs.map((run) => {
      const values = {},
        definitions = {}
      for (const [p, v] of Object.entries(flatten(run.record.parameters)))
        values[parameter(p, v)] = v
      const add = (path, metrics, defs) => {
        for (const [name, v] of Object.entries(metrics ?? {})) {
          const definition = defs?.[name] ?? {},
            unit = definition.unit || 'unknown'
          const id = `m:${JSON.stringify([...path, name, unit])}`
          const scope =
            path[0] === 'run'
              ? 'Run'
              : `${path[0] === 'actors' ? 'Actor' : 'Microgrid'}: ${path.slice(1).join(' / ')}`
          columns.set(id, {
            id,
            kind: 'metric',
            metricPath: path,
            label: human(name),
            scope,
            unit,
            numeric: true,
          })
          values[id] = numeric(v) ? v : null
          definitions[id] = definition
        }
      }
      const r = run.record
      add(['run'], r.metrics.run, r.metric_definitions.run)
      for (const [grid, metrics] of Object.entries(r.metrics.microgrids))
        add(
          ['microgrids', grid],
          metrics,
          r.metric_definitions.microgrids[grid],
        )
      for (const [grid, actors] of Object.entries(r.metrics.actors))
        for (const [actor, metrics] of Object.entries(actors))
          add(
            ['actors', grid, actor],
            metrics,
            r.metric_definitions.actors[grid]?.[actor],
          )
      return {
        ...run,
        run_id: run.record.run_id,
        key: run.record.run_id,
        name: run.record.run_id,
        configuration: c,
        values,
        definitions,
      }
    }),
  )
  for (const c of configurations) c.runs = []
  for (const run of runs) run.configuration.runs.push(run)
  for (const column of columns.values()) {
    if (column.kind === 'parameter')
      column.fixed =
        new Set(runs.map((r) => stable(r.values[column.id]))).size === 1
  }
  if (new Set(runs.map((r) => r.key)).size !== runs.length)
    throw new Error('A run appears more than once in this study.')
  const microgrids = [
    ...new Set(
      runs.flatMap((run) => [
        ...Object.keys(run.record.config?.microgrids || {}),
        ...Object.keys(run.record.metrics.microgrids || {}),
        ...Object.keys(run.record.metrics.actors || {}),
      ]),
    ),
  ]
  return {
    ...study,
    name: study.name || study.study_id,
    configurations,
    runs,
    microgrids,
    singleMicrogrid: microgrids.length === 1,
    columns: [...columns.values()],
  }
}
export function metricCategory(column) {
  const name = column.label.toLowerCase(),
    unit = column.unit || ''
  if (/carbon|emission|co2/.test(name) || /CO2/i.test(unit)) return 'Carbon'
  if (
    /cost|revenue|capex|opex|profit|price/.test(name) ||
    /^(EUR|USD|GBP|€|\$|£)(\/|$)/.test(unit)
  )
    return 'Cost'
  if (
    /energy|power|grid import|grid export/.test(name) ||
    /^(k|M|G|T)?Wh?$/.test(unit)
  )
    return 'Energy'
  return 'Other results'
}
export function columnGroups(columns, singleMicrogrid = false) {
  const groups = new Map()
  for (const column of columns) {
    // Explicit presentation grouping; these remain recorded input parameters.
    const path =
      column.kind === 'parameter'
        ? [
            column.fixed
              ? 'settings'
              : column.configurationInput
                ? 'configuration'
                : 'inputs',
          ]
        : singleMicrogrid &&
            ['run', 'microgrids'].includes(column.metricPath[0])
          ? ['results', metricCategory(column)]
          : column.metricPath
    const key = JSON.stringify(path)
    if (!groups.has(key)) {
      const labels = {
        configuration: 'Configuration inputs',
        inputs: 'Run inputs',
        run: 'Whole-system results',
        microgrids: 'Microgrid results',
        actors: 'Actor results',
        settings: 'Fixed inputs',
      }
      groups.set(key, {
        label:
          path[0] === 'results'
            ? path[1]
            : [
                labels[path[0]],
                ...path.slice(
                  singleMicrogrid && ['actors', 'microgrids'].includes(path[0])
                    ? 2
                    : 1,
                ),
              ].join(' · '),
        order:
          path[0] === 'results'
            ? 2 +
              ['Energy', 'Cost', 'Carbon', 'Other results'].indexOf(path[1]) /
                10
            : [
                'configuration',
                'inputs',
                'run',
                'microgrids',
                'actors',
                'settings',
              ].indexOf(path[0]),
        columns: [],
      })
    }
    groups.get(key).columns.push(column)
  }
  return [...groups.values()]
    .sort(
      (a, b) =>
        a.order - b.order ||
        a.label.localeCompare(b.label, undefined, { numeric: true }),
    )
    .map((group) => ({
      ...group,
      columns: group.columns.sort((a, b) => {
        if (a.kind !== 'metric' || b.kind !== 'metric')
          return a.label.localeCompare(b.label, undefined, { numeric: true })
        const categories = ['Energy', 'Cost', 'Carbon', 'Other results']
        return (
          categories.indexOf(metricCategory(a)) -
            categories.indexOf(metricCategory(b)) ||
          a.label.localeCompare(b.label, undefined, { numeric: true }) ||
          a.id.localeCompare(b.id)
        )
      }),
    }))
}
export function visibleSignals(signals, recordings) {
  const redundant = new Set(),
    gridPowers = new Set()
  for (const signal of signals.filter((s) => s.field === 'p_grid')) {
    const relevant = recordings.filter((r) =>
      r.series.some((s) => s.grid === signal.grid),
    )
    const replacements = relevant.map((r) => {
      const grids =
        r.config?.microgrids?.[signal.grid]?.dispatchables?.filter(
          (d) => d.type === 'GridConnection',
        ) || []
      if (grids.length !== 1) return null
      const name = grids[0].name.replaceAll('%', '%25').replaceAll('.', '%2E')
      return r.series.find(
        (s) =>
          s.grid === signal.grid &&
          s.field === `dispatch_states.${name}.current_power`,
      )
    })
    if (
      relevant.length &&
      replacements.every(Boolean) &&
      new Set(replacements.map((s) => s.id)).size === 1
    ) {
      redundant.add(signal.id)
      gridPowers.add(replacements[0].id)
    }
  }
  return signals
    .filter((s) => !redundant.has(s.id))
    .map((s) => ({
      ...s,
      gridPower: s.field === 'p_grid' || gridPowers.has(s.id),
    }))
}
export function signalGroups(signals) {
  const labels = [
    'Dispatchables',
    'Actors',
    'Grid inputs',
    'Policy',
    'Other signals',
  ]
  const sites = new Map()
  for (const signal of signals) {
    const prefix = signal.field.split('.')[0]
    const label =
      signal.field === 'p_grid'
        ? 'Dispatchables'
        : signal.field === 'p_delta'
          ? 'Actors'
          : {
              dispatch_states: 'Dispatchables',
              actor_states: 'Actors',
              grid_signals: 'Grid inputs',
              policy_state: 'Policy',
            }[prefix] || 'Other signals'
    if (!sites.has(signal.grid)) sites.set(signal.grid, new Map())
    const groups = sites.get(signal.grid)
    if (!groups.has(label)) groups.set(label, [])
    groups.get(label).push(signal)
  }
  return [...sites]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([site, groups]) => ({
      site,
      groups: labels
        .filter((label) => groups.has(label))
        .map((label) => ({
          label,
          signals: groups
            .get(label)
            .sort(
              (a, b) =>
                Number(b.field === 'p_delta') - Number(a.field === 'p_delta'),
            ),
        })),
    }))
}
export const columnLabel = (c) =>
  `${c.scope} · ${c.label}${c.unit && c.unit !== '1' ? ` (${c.unit})` : ''}`
export function sample(config, column) {
  const completed = config.runs.filter(
    (r) => r.record.execution.status === 'completed',
  )
  const candidates = completed.filter((r) => numeric(r.values[column.id]))
  if (column.kind === 'parameter')
    return { points: [], excluded: 0, reason: '' }
  const signatures = new Set(
    [...new Set(candidates.map((r) => r.definitions[column.id]))].map(stable),
  )
  const horizons = new Set(
    candidates.map((r) => r.record.execution.simulated_duration),
  )
  const expected = config.conditions?.duration_s
  let reason = ''
  if (column.unit === 'unknown') reason = 'Unit not recorded'
  else if (signatures.size > 1) reason = 'Definitions differ'
  else if (
    horizons.size > 1 ||
    candidates.some(
      (r) =>
        !numeric(r.record.execution.simulated_duration) ||
        (numeric(expected) &&
          r.record.execution.simulated_duration !== expected),
    )
  )
    reason = 'Horizons differ or are unknown'
  return {
    points: reason
      ? []
      : candidates.map((r) => ({ value: r.values[column.id], run: r })),
    excluded: config.runs.length - candidates.length,
    reason,
  }
}
export function cell(entity, column, statistic = 'median') {
  if (!entity.runs || column.kind === 'parameter')
    return entity.values[column.id] ?? null
  const values = sample(entity, column)
    .points.map((p) => p.value)
    .sort((a, b) => a - b)
  if (!values.length) return null
  if (statistic === 'mean')
    return values.reduce((a, b) => a + b, 0) / values.length
  if (statistic === 'min') return values[0]
  if (statistic === 'max') return values.at(-1)
  if (statistic === 'median')
    return values.length % 2
      ? values[(values.length - 1) / 2]
      : (values[values.length / 2 - 1] + values[values.length / 2]) / 2
  return null
}
