import ReactECharts from 'echarts-for-react'
import type { MicrogridState } from '../../api/types'
import { CHART_HEIGHT, formatTime, formatW, getBaseOption } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

export function GridChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const base = getBaseOption(isDark)

  const option = {
    ...base,
    visualMap: {
      show: false,
      type: 'piecewise',
      seriesIndex: 0,
      pieces: [
        { gte: 0, color: '#ef4444' },  // importing = red
        { lt: 0, color: '#22c55e' },   // exporting = green
      ],
    },
    tooltip: {
      ...base.tooltip,
      formatter: (params: { value: [string, number] }[]) => {
        if (!params.length) return ''
        const [time, val] = params[0].value
        const label = val > 0 ? 'importing' : val < 0 ? 'exporting' : 'balanced'
        const color = val > 0 ? '#ef4444' : val < 0 ? '#22c55e' : '#9ca3af'
        return `${formatTime(time)}<br/><span style="color:${color}"><b>${formatW(Math.abs(val))}</b></span> <span style="color:#9ca3af">${label}</span>`
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
        data: history.map((s) => [s.time, s.p_grid]),
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
