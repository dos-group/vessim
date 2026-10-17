// Shared, DOM-free analysis helpers for the interactive prototype.
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
      configurationInput: configurationInput || prior?.configurationInput || false,
      label: JSON.parse(path).map(human).join(' / '),
      scope: 'Parameter',
      unit: '',
      numeric: numeric(value) || prior?.numeric,
    })
    return id
  }
  const configurations = study.configurations.map((c) => ({
    ...c,
    key: c.configuration_id,
    values: Object.fromEntries(
      Object.entries(flatten(c.parameters)).map(([p, v]) => [
        parameter(p, v, true),
        v,
      ]),
    ),
  }))
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
        key: run.run_id,
        name: run.run_id,
        configuration: c,
        values,
        definitions,
      }
    }),
  )
  for (const c of configurations)
    c.runs = runs.filter((r) => r.configuration === c)
  return { ...study, configurations, runs, columns: [...columns.values()] }
}
export function columnGroups(columns) {
  const groups = new Map()
  for (const column of columns) {
    // Explicit presentation grouping; these remain recorded input parameters.
    const simulationSetting = column.parameterPath?.length === 1 &&
      ['days', 'step_seconds', 'input_model_version'].includes(column.parameterPath[0])
    const path = column.kind === 'parameter'
      ? [simulationSetting ? 'settings' : column.configurationInput ? 'configuration' : 'inputs']
      : column.metricPath
    const key = JSON.stringify(path)
    if (!groups.has(key)) {
      const labels = {
        configuration: 'Configuration inputs',
        inputs: 'Run inputs',
        run: 'Run results',
        microgrids: 'Microgrid results',
        actors: 'Actor results',
        settings: 'Simulation settings',
      }
      groups.set(key, {
        label: [labels[path[0]], ...path.slice(1)].join(' · '),
        order: ['configuration', 'inputs', 'run', 'microgrids', 'actors', 'settings'].indexOf(path[0]),
        columns: [],
      })
    }
    groups.get(key).columns.push(column)
  }
  return [...groups.values()].sort((a, b) => a.order - b.order)
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
    candidates.map((r) => stable(r.definitions[column.id])),
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
