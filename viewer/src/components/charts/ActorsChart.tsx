import ReactECharts from 'echarts-for-react'
import type { MicrogridState } from '../../api/types'
import { CHART_HEIGHT, PRODUCER_COLORS, CONSUMER_COLORS, formatTime, formatW, getBaseOption, connectChart } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  mode: 'producers' | 'consumers'
  height?: number
  stacked?: boolean
}

export function ActorsChart({ history, mode, height = CHART_HEIGHT, stacked = false }: Props) {
  const { isDark } = useTheme()

  const actorNames = Array.from(
    new Set(
      history.flatMap((s) =>
        Object.entries(s.actor_states)
          .filter(([, a]) => (mode === 'producers' ? a.power >= 0 : a.power < 0))
          .map(([name]) => name)
      )
    )
  )

  const colors = mode === 'producers' ? PRODUCER_COLORS : CONSUMER_COLORS

  const option = {
    ...getBaseOption(isDark),
    tooltip: {
      ...getBaseOption(isDark).tooltip,
      formatter: (params: { seriesName: string; value: [string, number] }[]) => {
        if (!params.length) return ''
        const time = formatTime(params[0].value[0])
        const rows = params
          .map((p) => `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${colors[actorNames.indexOf(p.seriesName) % colors.length]};margin-right:4px"></span>${p.seriesName}: <b>${formatW(p.value[1])}</b>`)
          .join('<br/>')
        return `${time}<br/>${rows}`
      },
    },
    series: actorNames.map((name, i) => ({
      name,
      type: 'line',
      stack: stacked ? 'total' : undefined,
      data: history.map((s) => [s.time, Math.abs(s.actor_states[name]?.power ?? 0)]),
      smooth: false,
      symbol: 'none',
      lineStyle: { color: colors[i % colors.length], width: 1.5 },
      areaStyle: { color: colors[i % colors.length], opacity: stacked ? (isDark ? 0.5 : 0.4) : (isDark ? 0.12 : 0.08) },
      emphasis: { focus: 'series' },
    })),
    yAxis: {
      ...getBaseOption(isDark).yAxis,
      axisLabel: {
        ...(getBaseOption(isDark).yAxis as { axisLabel: object }).axisLabel,
        formatter: (v: number) => formatW(v),
      },
    },
  }

  if (actorNames.length === 0) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-sm text-gray-400 dark:text-gray-600">
        No {mode === 'producers' ? 'producers' : 'consumers'}
      </div>
    )
  }

  return <ReactECharts option={option} style={{ height, width: '100%' }} notMerge onChartReady={connectChart} />
}
