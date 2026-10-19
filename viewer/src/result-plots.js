import { paretoFront } from './pareto.js'
import { sample, cell, numeric, stable, human } from './model.js'
import { summarize, empiricalDistribution } from './uncertainty.js'
import { presentation, fmt } from './presentation.js'

export function resultPlot(study, current, rows) {
  const { field, value, unit } = presentation(study, current)
  const selected = () => current[current.mode === 'runs' ? 'runs' : 'configs']
  const configColor = (config) => current.configColors[config.key]
  let note = ''
  let option = null,
    empty = ''
  const setOption = (settings) => {
    option = settings
  }
  function resultZoom() {
    const s = current,
      key = `${s.plotType}/${s.x}/${s.y}`
    const zoom = s.plotZoomKey === key ? s.plotZoom : []
    const axes =
      s.plotType === 'distribution'
        ? [{ yAxisIndex: 0 }]
        : s.plotType === 'ecdf'
          ? [{ xAxisIndex: 0 }]
          : [{ xAxisIndex: 0 }, { yAxisIndex: 0 }]
    return axes.map((axis, i) => ({
      type: 'inside',
      ...axis,
      filterMode: 'none',
      start: 0,
      end: 100,
      ...zoom[i],
    }))
  }
  function plotOverview(points, limit = 10000) {
    if (points.length <= limit) return points
    const stride = points.length / limit
    return Array.from(
      { length: limit },
      (_, i) => points[Math.floor(i * stride)],
    )
  }
  function renderDistribution(rows) {
    const s = current,
      metric = field(s.y),
      summaryMode = s.mode === 'configurations'
    if (!metric) {
      note = 'No numeric metrics recorded.'
      return
    }
    const configurations = summaryMode
      ? rows
      : [...new Set(rows.map((r) => r.configuration))]
    const shown = configurations.slice(0, 50),
      dots = [],
      centers = [],
      ranges = []
    let excluded = 0
    shown.forEach((config, i) => {
      const sampled = sample(config, metric)
      const runs = summaryMode
        ? sampled.points.map((p) => p.run)
        : rows.filter((r) => r.configuration === config)
      if (summaryMode && sampled.reason) {
        excluded += config.runs.length
        return
      }
      const valid = runs.filter((r) => numeric(cell(r, metric)))
      excluded +=
        (summaryMode ? config.runs.length : runs.length) - valid.length
      const values = valid.map((r) => value(metric, cell(r, metric)))
      valid.forEach((run, j) =>
        dots.push({
          key: summaryMode ? config.key : run.key,
          name: `${config.name}\n${run.key}${run.record.parameters.seed == null ? '' : ` · seed ${run.record.parameters.seed}`}\n${fmt(values[j])} ${unit(metric)}`,
          value: [i, values[j]],
          symbolOffset: [
            (j - (valid.length - 1) / 2) *
              Math.min(7, 36 / Math.max(1, valid.length - 1)),
            0,
          ],
          symbolSize: !summaryMode && s.runs.has(run.key) ? 11 : 7,
          itemStyle: {
            color: configColor(config),
            opacity: summaryMode ? 0.25 : 0.85,
          },
        }),
      )
      if (summaryMode && values.length) {
        const stats = summarize(values, s.stat, s.spread)
        centers.push({
          key: config.key,
          value: [i, stats.center],
          symbolSize: s.configs.has(config.key) ? 17 : 12,
          name: `${config.name}\n${human(s.stat)}: ${fmt(stats.center)} ${unit(metric)}\n${stats.count}/${config.runs.length} runs`,
          itemStyle: { color: configColor(config) },
        })
        if (stats.low !== null)
          ranges.push({
            value: [i, stats.low, stats.high],
            itemStyle: { color: configColor(config) },
          })
      }
    })
    setOption({
      tooltip: {
        trigger: 'item',
        renderMode: 'richText',
        confine: true,
        formatter: (p) => p.name,
      },
      dataZoom: resultZoom(),
      grid: { left: 85, right: 35, top: 28, bottom: 65 },
      xAxis: {
        type: 'category',
        data: shown.map((c) => c.name),
        boundaryGap: true,
        axisLabel: { hideOverlap: true },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        name: `${metric.label}${unit(metric) ? ` (${unit(metric)})` : ''}`,
        scale: true,
        splitLine: { lineStyle: { color: '#e4e9e6' } },
      },
      series: [
        {
          type: 'custom',
          silent: true,
          clip: true,
          encode: { x: 0, y: [1, 2] },
          data: ranges,
          renderItem: (params, api) => {
            const a = api.coord([api.value(0), api.value(1)]),
              b = api.coord([api.value(0), api.value(2)])
            const style = { stroke: api.visual('color'), lineWidth: 2 }
            return {
              type: 'group',
              children: [
                {
                  type: 'line',
                  shape: { x1: a[0], y1: a[1], x2: b[0], y2: b[1] },
                  style,
                },
                ...[a, b].map((p) => ({
                  type: 'line',
                  shape: { x1: p[0] - 5, y1: p[1], x2: p[0] + 5, y2: p[1] },
                  style,
                })),
              ],
            }
          },
        },
        {
          name: 'Individual runs',
          type: 'scatter',
          data: summaryMode && !s.plotIndividuals ? [] : plotOverview(dots),
          z: 3,
        },
        {
          name: human(s.stat),
          type: 'scatter',
          symbol: 'diamond',
          data: centers,
          z: 4,
        },
      ],
    })
    const definitions = new Set(
      shown.flatMap((c) =>
        c.runs
          .filter((r) => numeric(r.values[metric.id]))
          .map((r) =>
            stable([
              r.definitions[metric.id],
              r.record.execution.simulated_duration,
            ]),
          ),
      ),
    )
    note = `${summaryMode ? `${human(s.stat)} markers${s.spread === 'none' ? '' : s.spread === 'iqr' ? ' and middle 50% ranges' : ' and observed ranges'}${s.plotIndividuals ? '; faint dots are individual runs' : ''}.` : 'Each dot is one run; colors identify configurations.'} ${excluded ? `${excluded} values missing or incompatible. ` : ''}${configurations.length > shown.length ? `Showing the first ${shown.length} of ${configurations.length} configurations; filter to narrow the plot.` : ''}${definitions.size > 1 ? ' Metric definitions or durations differ; inspect recorded assumptions before comparison.' : ''}`
    if (dots.length > 10000 && (!summaryMode || s.plotIndividuals))
      note += ` Showing 10,000 of ${dots.length.toLocaleString()} run points. Summaries use all runs.`
  }

  function renderOutcomeDistribution(rows) {
    const s = current,
      metric = field(s.y)
    if (!metric) {
      note = 'No numeric metrics recorded.'
      return
    }
    const configurations =
      s.mode === 'configurations'
        ? rows
        : [...new Set(rows.map((r) => r.configuration))]
    const shown = configurations.slice(0, 12),
      curves = []
    let excluded = 0
    for (const config of shown) {
      const runs =
        s.mode === 'configurations'
          ? config.runs
          : rows.filter((r) => r.configuration === config)
      const sampled = sample({ ...config, runs }, metric)
      if (sampled.reason) {
        excluded += runs.length
        continue
      }
      excluded += runs.length - sampled.points.length
      const values = sampled.points.map((p) => value(metric, p.value))
      const points = empiricalDistribution(values)
      if (points.length) curves.push({ config, points, count: values.length })
    }
    if (!curves.length) {
      empty =
        'No comparable recorded values for this metric. Try another metric or configuration.'
      note = `${excluded} values missing or incompatible.`
      return
    }
    const low = Math.min(...curves.map((c) => c.points[0][0]))
    const high = Math.max(...curves.map((c) => c.points.at(-1)[0]))
    setOption({
      tooltip: {
        trigger: 'item',
        renderMode: 'richText',
        confine: true,
        formatter: (p) => p.name,
      },
      legend: { type: 'scroll', top: 0, left: 0, right: 0 },
      dataZoom: resultZoom(),
      grid: { left: 85, right: 35, top: 55, bottom: 65 },
      xAxis: {
        type: 'value',
        name: `${metric.label}${unit(metric) ? ` (${unit(metric)})` : ''}`,
        nameLocation: 'middle',
        nameGap: 38,
        scale: true,
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        name: 'Runs at or below (%)',
        axisLabel: { formatter: '{value}%' },
        splitLine: { lineStyle: { color: '#e4e9e6' } },
      },
      series: curves.map(({ config, points, count }) => ({
        name: `${config.name} (n=${count})`,
        type: 'line',
        step: 'end',
        showSymbol: true,
        symbolSize: 6,
        lineStyle: { width: 2, color: configColor(config) },
        itemStyle: { color: configColor(config) },
        data: [[low, 0], ...points, [high, 100]].map(([x, y]) => ({
          value: [x, y],
          name: `${config.name}\n${fmt(y)}% of ${count} runs at or below ${fmt(x)} ${unit(metric)}`,
        })),
      })),
    })
    const signatures = new Set(
      shown.flatMap((c) =>
        c.runs
          .filter((r) => numeric(r.values[metric.id]))
          .map((r) =>
            stable([
              r.definitions[metric.id],
              r.record.execution.simulated_duration,
            ]),
          ),
      ),
    )
    note =
      'Each step shows the share of recorded runs at or below a metric value. Curves use individual outcomes, with no fitted distribution.'
    if (excluded) note += ` ${excluded} values missing or incompatible.`
    if (configurations.length > shown.length)
      note += ` Showing the first ${shown.length} configurations. Filter the results to narrow the plot.`
    if (signatures.size > 1)
      note +=
        ' Metric definitions or durations differ. Inspect recorded assumptions before comparison.'
  }

  function renderScatter(rows) {
    const s = current,
      x = field(s.x),
      y = field(s.y)
    if (!x || !y) {
      note = 'No numeric parameters or metrics recorded.'
      return
    }
    if (
      s.mode === 'configurations' &&
      !s.stat &&
      [x, y].some((c) => c.kind === 'metric')
    ) {
      empty =
        'Choose a metric summary above to plot one point per configuration, or switch to Runs to plot recorded values directly.'
      return
    }
    const points = rows
      .map((e) => ({
        name: e.name,
        key: e.key,
        paint: study.singleRun
          ? undefined
          : configColor(e.runs ? e : e.configuration),
        value: [value(x, cell(e, x, s.stat)), value(y, cell(e, y, s.stat))],
      }))
      .filter((p) => p.value.every(numeric))
    note = `${points.length} points · ${rows.length - points.length} omitted for missing or incompatible values. Click a point to select it; use the table to open details.${s.mode === 'configurations' ? ` ${human(s.stat)} of completed runs; counts are shown in the table.${s.plotIndividuals ? ' Faint points show individual runs.' : ''}` : ''}`
    if ([x, y].some((c) => c.kind === 'parameter'))
      note +=
        ' Other inputs may vary between configurations. Points show recorded outcomes, not an isolated causal effect.'
    const pointKeys = new Set(points.map((p) => p.key))
    const comparedRuns = rows
      .filter((e) => pointKeys.has(e.key))
      .flatMap((e) => e.runs || [e])
    const definitionsVary = [x, y].some(
      (c) =>
        c.kind === 'metric' &&
        new Set(
          comparedRuns
            .filter((r) => numeric(r.values[c.id]))
            .map((r) =>
              stable([
                r.definitions[c.id],
                r.record.execution.simulated_duration,
              ]),
            ),
        ).size > 1,
    )
    if (definitionsVary)
      note +=
        ' Recorded metric definitions or durations differ. Review assumptions in run details.'
    const front =
      s.pareto && !definitionsVary
        ? paretoFront(points, s.paretoX, s.paretoY)
        : []
    if (s.pareto) {
      if (definitionsVary)
        note += ' Pareto front unavailable for incompatible results.'
      else
        note += ` Pareto front: ${front.length} nondominated ${s.mode === 'configurations' ? `${s.stat} summaries` : 'runs'} among the filtered points. Horizontal: ${s.paretoX === 'min' ? 'minimize' : 'maximize'}. Vertical: ${s.paretoY === 'min' ? 'minimize' : 'maximize'}.`
    }
    const individualCount =
      s.mode === 'configurations' && s.plotIndividuals
        ? rows.reduce((count, config) => count + config.runs.length, 0)
        : points.length
    if (individualCount > 10000)
      note += ` Showing a 10,000-point overview of ${individualCount.toLocaleString()} runs. Summaries and the Pareto front use all filtered results.`
    setOption({
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
              color: study.singleRun
                ? selected().has(p.key)
                  ? '#b65429'
                  : '#087f72'
                : p.paint,
              opacity: 0.8,
            },
          })),
        },
        ...(s.mode === 'configurations' && s.plotIndividuals
          ? [
              {
                name: 'Individual runs',
                type: 'scatter',
                z: 1,
                symbolSize: 6,
                data: plotOverview(
                  rows
                    .flatMap((config) =>
                      config.runs.map((run) => ({
                        key: config.key,
                        name: `${config.name} · ${run.key}${run.record.parameters.seed == null ? '' : ` · seed ${run.record.parameters.seed}`}`,
                        value: [value(x, cell(run, x)), value(y, cell(run, y))],
                        itemStyle: { color: configColor(config), opacity: 0.2 },
                      })),
                    )
                    .filter((p) => p.value.every(numeric)),
                ),
              },
            ]
          : []),
        ...(front.length
          ? [
              {
                name: 'Pareto front',
                type: 'line',
                z: 5,
                showSymbol: true,
                symbol: 'emptyCircle',
                symbolSize: 12,
                lineStyle: { color: '#263f38', width: 1.5, type: 'dashed' },
                itemStyle: { color: '#263f38', borderWidth: 2 },
                data: front,
              },
            ]
          : []),
      ],
    })
  }

  if (current.plotType === 'distribution') renderDistribution(rows)
  else if (current.plotType === 'ecdf') renderOutcomeDistribution(rows)
  else renderScatter(rows)
  return { option, note: note, empty }
}
