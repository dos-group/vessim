import Papa from 'papaparse'
function timestamp(raw) {
  const text = String(raw).replace(' ', 'T')
  return Date.parse(/(?:Z|[+-]\d\d:?\d\d)$/.test(text) ? text : `${text}Z`)
}
function unit(field) {
  if (
    field === 'p_grid' ||
    field === 'p_delta' ||
    /^actor_states\.[^.]+\.power$/.test(field) ||
    /^dispatch_states\.[^.]+\.current_power$/.test(field)
  )
    return 'W'
  if (/^dispatch_states\.[^.]+\.soc$/.test(field)) return '1'
  if (/^dispatch_states\.[^.]+\.charge_level$/.test(field)) return 'Wh'
  return 'unknown'
}
function reduce(points) {
  // Keep a full hourly year available when zooming into individual days.
  if (points.length <= 10000) return points
  const result = [points[0]],
    size = Math.ceil(points.length / 1300)
  for (let i = 1; i < points.length - 1; i += size) {
    let min = -1,
      max = -1,
      gap = -1
    for (let j = i; j < Math.min(i + size, points.length - 1); j++) {
      if (points[j][1] === null) {
        if (gap < 0) gap = j
        continue
      }
      if (min < 0 || points[j][1] < points[min][1]) min = j
      if (max < 0 || points[j][1] > points[max][1]) max = j
    }
    for (const k of [...new Set([min, max, gap])]
      .filter((k) => k >= 0)
      .sort((a, b) => a - b))
      result.push(points[k])
  }
  return [...result, points.at(-1)]
}
self.onmessage = async ({ data: { url } }) => {
  try {
    const response = await fetch(url)
    if (!response.ok)
      throw new Error(`Recording unavailable (${response.status})`)
    const groups = new Map()
    let malformed = 0,
      count = 0
    Papa.parse(await response.text(), {
      header: true,
      skipEmptyLines: 'greedy',
      dynamicTyping: (key) => !['time', 'microgrid'].includes(key),
      step: ({ data: row, errors }) => {
        const time = timestamp(row.time)
        if (
          errors.length ||
          !Number.isFinite(time) ||
          typeof row.microgrid !== 'string'
        ) {
          malformed++
          return
        }
        count++
        if (!groups.has(row.microgrid)) groups.set(row.microgrid, new Map())
        const fields = groups.get(row.microgrid)
        for (const [field, value] of Object.entries(row)) {
          if (
            typeof value === 'number' &&
            Number.isFinite(value) &&
            !fields.has(field)
          )
            fields.set(field, {
              id: JSON.stringify([row.microgrid, field]),
              grid: row.microgrid,
              field,
              unit: unit(field),
              points: [],
            })
        }
        for (const s of fields.values())
          s.points.push([
            time,
            typeof row[s.field] === 'number' && Number.isFinite(row[s.field])
              ? row[s.field]
              : null,
          ])
      },
    })
    const series = [...groups.values()]
      .flatMap((group) => [...group.values()])
      .map((s) => {
        s.points.sort((a, b) => a[0] - b[0])
        return { ...s, count: s.points.length, points: reduce(s.points) }
      })
    self.postMessage({ series, count, malformed })
  } catch (error) {
    self.postMessage({ error: error.message })
  }
}
