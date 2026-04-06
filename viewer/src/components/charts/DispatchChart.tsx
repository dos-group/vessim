import ReactECharts from 'echarts-for-react'
import type { MicrogridState } from '../../api/types'
import { CHART_HEIGHT, formatTime, formatW, getBaseOption } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

function buildDispatchSeries(history: MicrogridState[]) {
  if (history.length < 2) return []

  const names = Array.from(
    new Set(history.flatMap((s) => (s.dispatch_states ? Object.keys(s.dispatch_states) : [])))
  )

  return names.map((name) => ({
    name,
    data: history.map((s, i) => {
      if (i === 0) return [s.time, 0]
      const prev = history[i - 1]
      const dtHours =
        (new Date(s.time).getTime() - new Date(prev.time).getTime()) / 3_600_000
      const curr = s.dispatch_states?.[name]?.charge_level ?? null
      const prevLevel = prev.dispatch_states?.[name]?.charge_level ?? null
      const power =
        curr !== null && prevLevel !== null && dtHours > 0
          ? (curr - prevLevel) / dtHours
          : 0
      return [s.time, power]
    }),
  }))
}

export function DispatchChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const base = getBaseOption(isDark)
  const series = buildDispatchSeries(history)

  const option = {
    ...base,
    visualMap: series.length === 1
      ? {
          show: false,
          type: 'piecewise',
          seriesIndex: 0,
          pieces: [
            { gte: 0, color: '#22c55e' },
            { lt: 0, color: '#f59e0b' },
          ],
        }
      : undefined,
    tooltip: {
      ...base.tooltip,
      formatter: (params: { seriesName: string; value: [string, number]; color: string }[]) => {
        if (!params.length) return ''
        const time = formatTime(params[0].value[0])
        const rows = params
          .map((p) => `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:4px"></span>${p.seriesName}: <b>${formatW(p.value[1])}</b>`)
          .join('<br/>')
        return `${time}<br/>${rows}`
      },
    },
    yAxis: {
      ...base.yAxis,
      axisLabel: {
        ...(base.yAxis as { axisLabel: object }).axisLabel,
        formatter: (v: number) => formatW(v),
      },
    },
    series: series.map((s, i) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1.5 },
      areaStyle: { opacity: isDark ? 0.2 : 0.12 },
      connectNulls: true,
      // When multiple dispatchables, use distinct colors; single handled by visualMap
      ...(series.length > 1
        ? { color: ['#22c55e', '#3b82f6', '#f59e0b', '#8b5cf6'][i % 4] }
        : {}),
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { color: isDark ? '#374151' : '#d1d5db', type: 'solid', width: 1 },
        data: [{ yAxis: 0 }],
        label: { show: false },
      },
    })),
  }

  return <ReactECharts option={option} style={{ height, width: '100%' }} notMerge />
}
