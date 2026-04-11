import ReactECharts from 'echarts-for-react/lib/core'
import type { MicrogridState } from '../../api/types'
import { echarts, CHART_HEIGHT, formatTime, formatW, getBaseOption, connectChart } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

const POS_COLOR = '#22c55e'
const NEG_COLOR = '#ef4444'
const ZERO_LINE = { silent: true, symbol: 'none', lineStyle: { type: 'solid' as const, width: 1 }, data: [{ yAxis: 0 }], label: { show: false } }

export function PowerBalanceChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const base = getBaseOption(isDark)
  const zeroColor = isDark ? '#374151' : '#d1d5db'

  const option = {
    ...base,
    tooltip: {
      ...base.tooltip,
      formatter: (params: { value: [string, number] }[]) => {
        if (!params.length) return ''
        const pos = params[0]?.value[1] ?? 0
        const neg = params[1]?.value[1] ?? 0
        const actual = pos + neg
        const color = actual >= 0 ? POS_COLOR : NEG_COLOR
        const label = actual >= 0 ? 'surplus' : 'deficit'
        return `${formatTime(params[0].value[0])}<br/><span style="color:${color}"><b>${formatW(actual)}</b></span> <span style="color:#9ca3af">${label}</span>`
      },
    },
    yAxis: { ...base.yAxis, axisLabel: { ...(base.yAxis as { axisLabel: object }).axisLabel, formatter: (v: number) => formatW(v) } },
    series: [
      {
        type: 'line', symbol: 'none',
        data: history.map((s) => [s.time, Math.max(0, s.p_delta)]),
        lineStyle: { color: POS_COLOR, width: 1.5 },
        areaStyle: { color: POS_COLOR, opacity: isDark ? 0.25 : 0.2 },
        markLine: { ...ZERO_LINE, lineStyle: { ...ZERO_LINE.lineStyle, color: zeroColor } },
      },
      {
        type: 'line', symbol: 'none',
        data: history.map((s) => [s.time, Math.min(0, s.p_delta)]),
        lineStyle: { color: NEG_COLOR, width: 1.5 },
        areaStyle: { color: NEG_COLOR, opacity: isDark ? 0.25 : 0.2 },
      },
    ],
  }

  return <ReactECharts echarts={echarts} option={option} style={{ height, width: '100%' }} notMerge onChartReady={connectChart} />
}
