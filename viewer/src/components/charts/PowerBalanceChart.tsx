import ReactECharts from 'echarts-for-react'
import type { MicrogridState } from '../../api/types'
import { CHART_HEIGHT, formatTime, formatW, getBaseOption } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

export function PowerBalanceChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const base = getBaseOption(isDark)

  const option = {
    ...base,
    visualMap: {
      show: false,
      type: 'piecewise',
      seriesIndex: 0,
      pieces: [
        { gte: 0, color: '#22c55e' },
        { lt: 0, color: '#ef4444' },
      ],
    },
    tooltip: {
      ...base.tooltip,
      formatter: (params: { value: [string, number] }[]) => {
        if (!params.length) return ''
        const [time, val] = params[0].value
        const color = val >= 0 ? '#22c55e' : '#ef4444'
        const label = val >= 0 ? 'surplus' : 'deficit'
        return `${formatTime(time)}<br/><span style="color:${color}"><b>${formatW(val)}</b></span> <span style="color:#9ca3af">${label}</span>`
      },
    },
    yAxis: {
      ...base.yAxis,
      axisLabel: {
        ...(base.yAxis as { axisLabel: object }).axisLabel,
        formatter: (v: number) => formatW(v),
      },
    },
    series: [
      {
        type: 'line',
        data: history.map((s) => [s.time, s.p_delta]),
        smooth: false,
        symbol: 'none',
        lineStyle: { width: 1.5 },
        areaStyle: { opacity: isDark ? 0.25 : 0.2 },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: isDark ? '#374151' : '#d1d5db', type: 'solid', width: 1 },
          data: [{ yAxis: 0 }],
          label: { show: false },
        },
      },
    ],
  }

  return <ReactECharts option={option} style={{ height, width: '100%' }} notMerge />
}
