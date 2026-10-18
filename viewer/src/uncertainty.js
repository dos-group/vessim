// Summaries of recorded values. Missing values are never imputed.
export function quantile(sorted, p) {
  if (!sorted.length) return null
  const at = (sorted.length - 1) * p, lo = Math.floor(at)
  return sorted[lo] + (sorted[Math.ceil(at)] - sorted[lo]) * (at - lo)
}
export function summarize(values, statistic = 'median', spread = 'range') {
  const sorted = values.filter(v => typeof v === 'number' && Number.isFinite(v)).sort((a, b) => a - b)
  const center = !sorted.length ? null : statistic === 'mean'
    ? sorted.reduce((a, b) => a + b, 0) / sorted.length
    : statistic === 'min' ? sorted[0] : statistic === 'max' ? sorted.at(-1) : quantile(sorted, 0.5)
  const bounds = spread === 'none' || !sorted.length ? [null, null]
    : spread === 'iqr' ? [quantile(sorted, 0.25), quantile(sorted, 0.75)] : [sorted[0], sorted.at(-1)]
  return { center, low: bounds[0], high: bounds[1], count: sorted.length }
}
export function empiricalDistribution(values) {
  const sorted = values.filter(v => typeof v === 'number' && Number.isFinite(v)).sort((a, b) => a - b)
  if (!sorted.length) return []
  const points = [[sorted[0], 0]]
  sorted.forEach((value, i) => {
    if (i === sorted.length - 1 || sorted[i + 1] !== value)
      points.push([value, (i + 1) / sorted.length * 100])
  })
  return points
}
export function summarizeTrajectories(series, statistic, spread) {
  if (!series.length) return []
  if (series.some(s => s.count > s.points.length))
    throw Error('Summary unavailable for reduced recordings. Use individual runs or record a coarser common time grid.')
  const times = series[0].points.map(p => p[0])
  if (series.some(s => s.points.length !== times.length || s.points.some((p, i) => p[0] !== times[i])))
    throw Error('Summary requires matching timestamps after time alignment. Use individual runs to inspect different time grids.')
  return times.map((t, i) => ({ time: t, ...summarize(series.map(s => s.points[i][1]), statistic, spread) }))
}
