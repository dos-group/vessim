/* global echarts */
import { summarizeTrajectories } from './uncertainty.js'
import { human } from './model.js'
import { inSelectionOrder } from './state.js'
import { displayUnit, inDisplayUnit, unitOptions } from './units.js'
function trajectorySeries(study, current, supported, spec) {
  const configColor = (config) => current.configColors[config.key]
  const color = (run) =>
    study.singleRun
      ? current.runColors[run.key]
      : configColor(run.configuration)
  const s = current,
    aggregate = !study.singleRun && s.timeMode === 'configurations'
  const line = (run, sig, faint = false) => ({
    id: run.key,
    name: `${run.name}${run.record.parameters.seed == null ? '' : ` · seed ${run.record.parameters.seed}`}`,
    type: 'line',
    step: 'end',
    showSymbol: false,
    connectNulls: false,
    lineStyle: {
      width: faint ? 1 : 1.6,
      color: color(run),
      opacity: faint ? 0.25 : 0.8,
    },
    itemStyle: { color: color(run) },
    data: sig.points.map(([t, v]) => [
      s.alignment === 'elapsed'
        ? (t - time(run.record.config.environment?.sim_start)) / 3600000
        : t,
      inDisplayUnit(v, spec),
    ]),
  })
  if (!aggregate)
    return {
      series: supported.map(({ run, signal }) => line(run, signal)),
      notes: [],
    }
  const series = [],
    notes = []
  for (const config of inSelectionOrder(study.configurations, s.timeConfigs)) {
    const matches = supported.filter((m) => m.run.configuration === config)
    if (!matches.length) continue
    try {
      const points = summarizeTrajectories(
        matches.map(({ run, signal }) => ({
          count: signal.count,
          points: line(run, signal).data,
        })),
        s.timeStat,
        s.timeSpread,
      )
      const counts = points.map((p) => p.count),
        min = Math.min(...counts),
        max = Math.max(...counts)
      notes.push(
        `${config.name}: ${min === max ? min : `${min}–${max}`}/${config.runs.length} runs per timestamp`,
      )
      const paint = configColor(config)
      if (s.timeSpread !== 'none')
        series.push({
          id: `band-${config.key}`,
          name: `${config.name} spread`,
          type: 'custom',
          silent: true,
          z: 1,
          encode: { x: [0, 3], y: [1, 2] },
          data: points
            .slice(0, -1)
            .flatMap((p, i) =>
              p.low === null || points[i + 1].low === null
                ? []
                : [[p.time, p.low, p.high, points[i + 1].time]],
            ),
          renderItem: (params, api) => {
            const coords = [
              [api.value(0), api.value(1)],
              [api.value(3), api.value(1)],
              [api.value(3), api.value(2)],
              [api.value(0), api.value(2)],
            ].map((p) => api.coord(p))
            return {
              type: 'polygon',
              shape: {
                points: echarts.graphic.clipPointsByRect(
                  coords,
                  params.coordSys,
                ),
              },
              style: { fill: paint, opacity: 0.16 },
            }
          },
        })
      if (s.timeIndividuals)
        series.push(
          ...matches.map(({ run, signal }) => line(run, signal, true)),
        )
      series.push({
        id: `summary-${config.key}`,
        name: `${config.name} · ${human(s.timeStat)}`,
        type: 'line',
        step: 'end',
        showSymbol: false,
        connectNulls: false,
        z: 4,
        lineStyle: { width: 2.2, color: paint },
        itemStyle: { color: paint },
        data: points.map((p) => ({
          value: [p.time, p.center],
          name: `${p.count}/${config.runs.length} runs`,
        })),
      })
    } catch (error) {
      notes.push(`${config.name}: ${error.message}`)
    }
  }
  return { series, notes }
}

export function time(raw) {
  if (typeof raw !== 'string') return NaN
  let s = raw.replace(' ', 'T')
  if (/^\d{4}-\d\d-\d\d$/.test(s)) s += 'T00:00:00'
  return Date.parse(/(?:Z|[+-]\d\d:?\d\d)$/.test(s) ? s : s + 'Z')
}

// Preparing points is independent of zoom and other controls, so React can
// reuse these arrays while changing the viewport.
export function prepareTrajectory(
  study,
  settings,
  signal,
  matches,
  preference,
) {
  const supported = matches.filter((m) => m.signal)
  const missing = matches.filter((m) => !m.signal).map((m) => m.run.key)
  const magnitude = supported.reduce(
    (max, m) =>
      m.signal.points.reduce(
        (max, p) => Math.max(max, Math.abs(p[1] || 0)),
        max,
      ),
    0,
  )
  const spec = displayUnit(
    signal.unit,
    magnitude,
    unitOptions(signal.unit).some((option) => option.unit === preference)
      ? preference
      : 'auto',
  )
  const error =
    signal.unit === 'unknown' && supported.length > 1
      ? 'Unit not recorded. Select a single run to inspect this signal.'
      : settings.alignment === 'elapsed' &&
          supported.some(
            (m) =>
              !Number.isFinite(
                time(m.run.record.config.environment?.sim_start),
              ),
          )
        ? 'Simulation start missing. Use recorded UTC time.'
        : ''
  return {
    missing,
    magnitude,
    spec,
    error,
    ...(error
      ? { series: [], notes: [] }
      : trajectorySeries(study, settings, supported, spec)),
  }
}
export function trajectoryOptions(series, alignment, zoom) {
  return {
    useUTC: true,
    tooltip: { trigger: 'axis', renderMode: 'richText', confine: true },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: { top: 20, left: 80, right: 30, bottom: 75 },
    xAxis: {
      type: alignment === 'elapsed' ? 'value' : 'time',
      name: alignment === 'elapsed' ? 'Hours' : 'UTC',
      nameGap: 35,
      nameLocation: 'middle',
      axisLabel: {
        hideOverlap: true,
        showMinLabel: false,
        showMaxLabel: false,
      },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#e5e9e7' } },
    },
    dataZoom: [
      { type: 'inside', filterMode: 'none', ...zoom },
      {
        type: 'slider',
        bottom: 4,
        height: 18,
        filterMode: 'none',
        ...zoom,
      },
    ],
    series: series,
  }
}
