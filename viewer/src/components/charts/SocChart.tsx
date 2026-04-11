import ReactECharts from 'echarts-for-react/lib/core'
import type { MicrogridState } from '../../api/types'
import { echarts, CHART_HEIGHT, formatTime, getBaseOption, connectChart } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

const SOC_COLOR = '#eab308'

export function SocChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const base = getBaseOption(isDark)

  const dispatchNames = Array.from(
    new Set(
      history.flatMap((s) =>
        s.dispatch_states
          ? Object.entries(s.dispatch_states)
              .filter(([, state]) => state.soc != null)
              .map(([name]) => name)
          : []
      )
    )
  )

  // Extract first non-null min_soc per dispatchable
  const minSocMap: Record<string, number> = {}
  for (const name of dispatchNames) {
    for (const s of history) {
      const ms = s.dispatch_states?.[name]?.min_soc
      if (ms != null) { minSocMap[name] = ms * 100; break }
    }
  }

  const option = {
    ...base,
    tooltip: {
      ...base.tooltip,
      formatter: (params: { seriesName: string; value: [string, number] }[]) => {
        if (!params.length) return ''
        const time = formatTime(params[0].value[0])
        const rows = params
          .filter((p) => !p.seriesName.startsWith('__'))
          .map((p) => `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${SOC_COLOR};margin-right:4px"></span>${p.seriesName}: <b>${p.value[1].toFixed(1)}%</b>`)
          .join('<br/>')
        return `${time}<br/>${rows}`
      },
    },
    yAxis: {
      ...base.yAxis,
      min: 0,
      max: 100,
      axisLabel: {
        ...(base.yAxis as { axisLabel: object }).axisLabel,
        formatter: (v: number) => `${v}%`,
      },
    },
    series: dispatchNames.map((name) => ({
      name,
      type: 'line',
      data: history.map((s) => {
        const soc = s.dispatch_states?.[name]?.soc
        return [s.time, soc != null ? soc * 100 : null]
      }),
      smooth: false,
      symbol: 'none',
      lineStyle: { color: SOC_COLOR, width: 1.5 },
      areaStyle: { color: SOC_COLOR, opacity: isDark ? 0.15 : 0.1 },
      connectNulls: true,
      ...(minSocMap[name] != null
        ? {
            markLine: {
              silent: true,
              symbol: 'none',
              lineStyle: { color: '#6b7280', type: 'dashed', width: 1 },
              label: {
                formatter: `Min SoC (${minSocMap[name].toFixed(0)}%)`,
                position: 'insideStartTop',
                color: '#6b7280',
                fontSize: 10,
                fontFamily: 'ui-monospace, monospace',
              },
              data: [{ yAxis: minSocMap[name] }],
            },
          }
        : {}),
    })),
  }

  return <ReactECharts echarts={echarts} option={option} style={{ height, width: '100%' }} notMerge onChartReady={connectChart} />
}
