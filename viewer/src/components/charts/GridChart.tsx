import ReactECharts from 'echarts-for-react'
import type { MicrogridState } from '../../api/types'
import { CHART_HEIGHT, formatTime, formatW, getBaseOption, connectChart } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

// p_grid > 0 = exporting (microgrid sends power to grid) = green
// p_grid < 0 = importing (grid provides power to microgrid) = red
const EXPORT_COLOR = '#22c55e'
const IMPORT_COLOR = '#ef4444'
const ZERO_LINE = { silent: true, symbol: 'none', lineStyle: { type: 'solid' as const, width: 1 }, data: [{ yAxis: 0 }], label: { show: false } }

export function GridChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const base = getBaseOption(isDark)
  const zeroColor = isDark ? '#374151' : '#d1d5db'

  const option = {
    ...base,
    tooltip: {
      ...base.tooltip,
      formatter: (params: { value: [string, number] }[]) => {
        if (!params.length) return ''
        const exporting = params[0]?.value[1] ?? 0
        const importing = params[1]?.value[1] ?? 0
        const actual = exporting + importing
        const label = actual > 0 ? 'exporting' : actual < 0 ? 'importing' : 'balanced'
        const color = actual > 0 ? EXPORT_COLOR : actual < 0 ? IMPORT_COLOR : '#9ca3af'
        return `${formatTime(params[0].value[0])}<br/><span style="color:${color}"><b>${formatW(Math.abs(actual))}</b></span> <span style="color:#9ca3af">${label}</span>`
      },
    },
    yAxis: { ...base.yAxis, axisLabel: { ...(base.yAxis as { axisLabel: object }).axisLabel, formatter: (v: number) => formatW(v) } },
    series: [
      {
        type: 'line', symbol: 'none',
        data: history.map((s) => [s.time, Math.max(0, s.p_grid)]),
        lineStyle: { color: EXPORT_COLOR, width: 1.5 },
        areaStyle: { color: EXPORT_COLOR, opacity: isDark ? 0.25 : 0.2 },
        markLine: { ...ZERO_LINE, lineStyle: { ...ZERO_LINE.lineStyle, color: zeroColor } },
      },
      {
        type: 'line', symbol: 'none',
        data: history.map((s) => [s.time, Math.min(0, s.p_grid)]),
        lineStyle: { color: IMPORT_COLOR, width: 1.5 },
        areaStyle: { color: IMPORT_COLOR, opacity: isDark ? 0.25 : 0.2 },
      },
    ],
  }

  return <ReactECharts option={option} style={{ height, width: '100%' }} notMerge onChartReady={connectChart} />
}
