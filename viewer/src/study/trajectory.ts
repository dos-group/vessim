import Papa from 'papaparse'
import { numeric } from './model.ts'

export type Point = [number, number | null]
export interface Series {
  id: string
  grid: string
  field: string
  unit: string
  points: Point[]
  count: number
}
export interface Trajectory {
  series: Series[]
  rows: number
  warnings: string[]
}
export function timestamp(value: unknown): number {
  if (value instanceof Date) return value.getTime()
  if (typeof value !== 'string') return NaN
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? `${value}T00:00:00`
    : value.replace(' ', 'T')
  return Date.parse(
    /(?:Z|[+-]\d\d:?\d\d)$/.test(normalized) ? normalized : `${normalized}Z`,
  )
}
export function fieldLabel(field: string): string {
  return field
    .split('.')
    .map((part) => part.replaceAll('%2E', '.').replaceAll('%25', '%'))
    .join(' / ')
}
export function unitFor(field: string): string {
  if (
    field === 'p_delta' ||
    field === 'p_grid' ||
    /^actor_states\.[^.]+\.power$/.test(field) ||
    /^dispatch_states\.[^.]+\.current_power$/.test(field)
  )
    return 'W'
  if (/^dispatch_states\.[^.]+\.charge_level$/.test(field)) return 'Wh'
  if (/^dispatch_states\.[^.]+\.soc$/.test(field)) return '1'
  return 'unknown'
}
// Preserve extrema and explicit gaps, rather than silently smoothing away peaks.
export function reducePoints(points: Point[], limit = 4000): Point[] {
  if (points.length <= limit) return points
  const reduced: Point[] = [points[0]]
  const size = Math.ceil(
    points.length / Math.max(1, Math.floor((limit - 2) / 3)),
  )
  for (let start = 1; start < points.length - 1; start += size) {
    const end = Math.min(points.length - 1, start + size)
    let min = -1,
      max = -1,
      gap = -1
    for (let i = start; i < end; i++) {
      const value = points[i][1]
      if (value === null) {
        if (gap < 0) gap = i
        continue
      }
      if (min < 0 || value < points[min][1]!) min = i
      if (max < 0 || value > points[max][1]!) max = i
    }
    for (const i of [...new Set([min, max, gap])]
      .filter((i) => i >= 0)
      .sort((a, b) => a - b))
      reduced.push(points[i])
  }
  reduced.push(points[points.length - 1])
  return reduced
}
export function parseTrajectory(text: string): Trajectory {
  const maps = new Map<string, Map<string, Series>>()
  const warnings: string[] = []
  let rows = 0,
    invalid = 0
  const add = (
    grid: string,
    time: unknown,
    values: Record<string, unknown>,
  ) => {
    const t = timestamp(time)
    if (!Number.isFinite(t)) {
      invalid++
      return
    }
    rows++
    let fields = maps.get(grid)
    if (!fields) {
      fields = new Map()
      maps.set(grid, fields)
    }
    for (const [field, value] of Object.entries(values)) {
      if (field === 'time' || field === 'microgrid' || !numeric(value)) continue
      if (!fields.has(field))
        fields.set(field, {
          id: JSON.stringify([grid, field]),
          grid,
          field,
          unit: unitFor(field),
          points: [],
          count: 0,
        })
    }
    for (const series of fields.values()) {
      const value = values[series.field]
      series.points.push([t, numeric(value) ? value : null])
    }
  }
  Papa.parse<Record<string, unknown>>(text, {
    header: true,
    // Identifiers and timestamps are strings even if they look like numbers/booleans.
    dynamicTyping: (field) => field !== 'microgrid' && field !== 'time',
    skipEmptyLines: 'greedy',
    step: (result) => {
      if (result.errors.length) {
        invalid++
        return
      }
      const row = result.data
      if (typeof row.microgrid !== 'string' || !row.microgrid) {
        invalid++
        return
      }
      add(row.microgrid, row.time, row)
    },
  })
  if (invalid)
    warnings.push(
      `${invalid.toLocaleString()} malformed rows or timestamps were skipped.`,
    )
  const series = [...maps.values()]
    .flatMap((fields) => [...fields.values()])
    .map((s) => {
      s.points.sort((a, b) => a[0] - b[0])
      s.count = s.points.length
      s.points = reducePoints(s.points)
      return s
    })
  if (series.some((s) => s.count > s.points.length))
    warnings.push(
      'Charts use an extrema-preserving overview of up to 4,000 points per signal. Download the recording for full-resolution analysis.',
    )
  return { series, rows, warnings }
}
