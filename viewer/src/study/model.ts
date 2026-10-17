export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json }
export interface Definition {
  unit: string
  description?: string
  assumptions?: Record<string, Json>
}
export interface Scopes<T> {
  run: Record<string, T>
  microgrids: Record<string, Record<string, T>>
  actors: Record<string, Record<string, Record<string, T>>>
}
export interface Experiment {
  format: 'vessim.experiment'
  schema_version: 1
  run_id: string
  parameters: Record<string, Json>
  config: {
    environment?: Record<string, Json>
    microgrids: Record<string, Json>
  }
  execution: {
    status: string
    simulated_duration?: number
    wall_time?: number
    steps?: number
    [key: string]: Json | undefined
  }
  metrics: Scopes<number | null>
  metric_definitions: Scopes<Definition>
}
export interface Entry {
  key: string
  source: string
  record: Experiment
  trajectory: { url: string } | null
}
export interface Column {
  id: string
  label: string
  scope: string
  kind: 'parameter' | 'metric'
  unit: string
  numeric: boolean
}
export interface Run extends Entry {
  values: Record<string, Json>
  definitions: Record<string, Definition>
  search: string
}
export interface Catalog {
  name: string
  runs: Run[]
  columns: Column[]
  errors: string[]
}
export interface WireCatalog {
  name: string
  runs: Entry[]
  errors: string[]
}

export function flatten(
  value: unknown,
  path: string[] = [],
  result: Record<string, Json> = {},
): Record<string, Json> {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    for (const [key, child] of Object.entries(value))
      flatten(child, [...path, key], result)
  } else if (path.length) result[JSON.stringify(path)] = (value ?? null) as Json
  return result
}
export const human = (value: string) => value.replaceAll('_', ' ')
export function stable(value: unknown): string {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return JSON.stringify(
      Object.fromEntries(
        Object.entries(value)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([k, v]) => [k, JSON.parse(stable(v))]),
      ),
    )
  }
  return JSON.stringify(value ?? null)
}
export function format(value: Json | undefined, unit = ''): string {
  if (value == null) return '—'
  const text =
    typeof value === 'number'
      ? value.toLocaleString(undefined, { maximumSignificantDigits: 6 })
      : typeof value === 'object'
        ? JSON.stringify(value)
        : String(value)
  return `${text}${unit && unit !== '1' ? ` ${unit}` : ''}`
}
export function numeric(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function indexCatalog(wire: WireCatalog): Catalog {
  const columns = new Map<string, Column>()
  const errors = [...(wire.errors ?? [])]
  const runs: Run[] = []
  for (const entry of wire.runs) {
    try {
      const record = entry.record
      if (
        record.format !== 'vessim.experiment' ||
        record.schema_version !== 1 ||
        typeof record.run_id !== 'string'
      )
        throw new Error('Unsupported experiment record')
      const values: Run['values'] = {}
      const definitions: Run['definitions'] = {}
      for (const [path, value] of Object.entries(flatten(record.parameters))) {
        const id = `parameter:${path}`
        values[id] = value
        const prior = columns.get(id)
        columns.set(id, {
          id,
          kind: 'parameter',
          label: (JSON.parse(path) as string[]).map(human).join(' / '),
          scope: 'Parameter',
          unit: '',
          numeric: numeric(value) || !!prior?.numeric,
        })
      }
      const add = (
        scope: string[],
        metrics: Record<string, number | null>,
        defs: Record<string, Definition>,
      ) => {
        for (const [name, value] of Object.entries(metrics)) {
          const def = defs?.[name]
          const unit = def?.unit || 'unknown'
          const id = `metric:${JSON.stringify([...scope, name, unit])}`
          values[id] = numeric(value) ? value : null
          definitions[id] = def ?? {
            unit,
            description: 'Metric definition not recorded.',
          }
          const scopeLabel =
            scope[0] === 'run'
              ? 'Run'
              : `${scope[0] === 'actors' ? 'Actor' : 'Microgrid'}: ${scope.slice(1).join(' / ')}`
          columns.set(id, {
            id,
            kind: 'metric',
            label: human(name),
            scope: scopeLabel,
            unit,
            numeric: true,
          })
        }
      }
      add(['run'], record.metrics.run, record.metric_definitions.run)
      for (const [grid, metrics] of Object.entries(record.metrics.microgrids))
        add(
          ['microgrids', grid],
          metrics,
          record.metric_definitions.microgrids[grid],
        )
      for (const [grid, actors] of Object.entries(record.metrics.actors)) {
        for (const [actor, metrics] of Object.entries(actors))
          add(
            ['actors', grid, actor],
            metrics,
            record.metric_definitions.actors[grid]?.[actor],
          )
      }
      runs.push({
        ...entry,
        values,
        definitions,
        search:
          `${record.run_id} ${entry.source} ${JSON.stringify(record.parameters)} ${record.execution.status}`.toLowerCase(),
      })
    } catch (e) {
      errors.push(`${entry.source}: ${String(e)}`)
    }
  }
  return { name: wire.name, runs, columns: [...columns.values()], errors }
}
export function columnLabel(c: Column) {
  return `${c.scope} · ${c.label}${c.unit && c.unit !== '1' ? ` (${c.unit})` : ''}`
}
export function delta(
  run: Run,
  baseline: Run,
  column: Column,
): { absolute: number; percent: number | null } | null {
  const value = run.values[column.id],
    base = baseline.values[column.id]
  if (!numeric(value) || !numeric(base)) return null
  if (
    column.kind === 'metric' &&
    (column.unit === 'unknown' ||
      run.definitions[column.id]?.unit !==
        baseline.definitions[column.id]?.unit)
  )
    return null
  return {
    absolute: value - base,
    percent: base === 0 ? null : ((value - base) / Math.abs(base)) * 100,
  }
}
// These differences provide context; they do not establish scientific comparability.
export function metricDifferences(
  run: Run,
  baseline: Run,
  column: Column,
): string[] {
  const definition = run.definitions[column.id]
  const reference = baseline.definitions[column.id]
  if (!definition || !reference) return []
  const differences: string[] = []
  if ((definition.description ?? '') !== (reference.description ?? ''))
    differences.push('Description differs')
  if (
    stable(definition.assumptions ?? {}) !== stable(reference.assumptions ?? {})
  )
    differences.push('Assumptions differ')
  return differences
}

export function csv(runs: Run[], columns: Column[]): string {
  const escape = (value: unknown) => {
    let text =
      value == null
        ? ''
        : typeof value === 'object'
          ? JSON.stringify(value)
          : String(value)
    // Protect spreadsheet users from formula interpretation in text fields.
    if (typeof value !== 'number' && /^[=+\-@\t\r]/.test(text))
      text = `'${text}`
    return `"${text.replaceAll('"', '""')}"`
  }
  return [
    ['run_id', 'source', 'status', ...columns.map(columnLabel)],
    ...runs.map((run) => [
      run.record.run_id,
      run.source,
      run.record.execution.status,
      ...columns.map((c) => run.values[c.id]),
    ]),
  ]
    .map((row) => row.map(escape).join(','))
    .join('\r\n')
}
export function download(name: string, content: string, type = 'text/csv') {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
