import ReactECharts from 'echarts-for-react'
import type { MicrogridState } from '../../api/types'
import { CHART_HEIGHT, formatTime, formatW, getBaseOption, connectChart } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

function buildDispatchData(history: MicrogridState[]) {
  if (history.length < 2) return []

  const names = Array.from(
    new Set(history.flatMap((s) => (s.dispatch_states ? Object.keys(s.dispatch_states) : [])))
  )

  return names.map((name) => ({
    name,
    values: history.map((s, i) => {
      if (i === 0) return [s.time, 0] as [string, number]
      const prev = history[i - 1]
      const dtHours = (new Date(s.time).getTime() - new Date(prev.time).getTime()) / 3_600_000
      const curr = s.dispatch_states?.[name]?.charge_level ?? null
      const prevLevel = prev.dispatch_states?.[name]?.charge_level ?? null
      const power = curr !== null && prevLevel !== null && dtHours > 0
        ? (curr - prevLevel) / dtHours : 0
      return [s.time, power] as [string, number]
    }),
  }))
}

// Charging = green, discharging = amber
const CHARGE_COLOR = '#22c55e'
const DISCHARGE_COLOR = '#f59e0b'
const ZERO_LINE = { silent: true, symbol: 'none', lineStyle: { type: 'solid' as const, width: 1 }, data: [{ yAxis: 0 }], label: { show: false } }

export function DispatchChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const base = getBaseOption(isDark)
  const zeroColor = isDark ? '#374151' : '#d1d5db'
  const dispatchables = buildDispatchData(history)

  // For a single dispatchable: split into charge/discharge series (same as balance/grid)
  // For multiple: use distinct colors per dispatchable
  const series = dispatchables.length === 1
    ? [
        {
          type: 'line', symbol: 'none',
          data: dispatchables[0].values.map(([t, v]) => [t, Math.max(0, v)]),
          lineStyle: { color: CHARGE_COLOR, width: 1.5 },
          areaStyle: { color: CHARGE_COLOR, opacity: isDark ? 0.25 : 0.2 },
          markLine: { ...ZERO_LINE, lineStyle: { ...ZERO_LINE.lineStyle, color: zeroColor } },
        },
        {
          type: 'line', symbol: 'none',
          data: dispatchables[0].values.map(([t, v]) => [t, Math.min(0, v)]),
          lineStyle: { color: DISCHARGE_COLOR, width: 1.5 },
          areaStyle: { color: DISCHARGE_COLOR, opacity: isDark ? 0.25 : 0.2 },
        },
      ]
    : dispatchables.map((d, i) => ({
        name: d.name,
        type: 'line', symbol: 'none',
        data: d.values,
        color: [CHARGE_COLOR, '#3b82f6', '#f59e0b', '#8b5cf6'][i % 4],
        lineStyle: { width: 1.5 },
        areaStyle: { opacity: isDark ? 0.2 : 0.12 },
        markLine: i === 0 ? { ...ZERO_LINE, lineStyle: { ...ZERO_LINE.lineStyle, color: zeroColor } } : undefined,
      }))

  const tooltip = {
    ...base.tooltip,
    formatter: dispatchables.length === 1
      ? (params: { value: [string, number] }[]) => {
          if (!params.length) return ''
          const charging = params[0]?.value[1] ?? 0
          const discharging = params[1]?.value[1] ?? 0
          const actual = charging + discharging
          const color = actual >= 0 ? CHARGE_COLOR : DISCHARGE_COLOR
          const label = actual > 0.5 ? 'charging' : actual < -0.5 ? 'discharging' : 'idle'
          return `${formatTime(params[0].value[0])}<br/><span style="color:${color}"><b>${formatW(Math.abs(actual))}</b></span> <span style="color:#9ca3af">${label}</span>`
        }
      : (params: { seriesName: string; value: [string, number]; color: string }[]) => {
          if (!params.length) return ''
          const time = formatTime(params[0].value[0])
          const rows = params.map((p) =>
            `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:4px"></span>${p.seriesName}: <b>${formatW(p.value[1])}</b>`
          ).join('<br/>')
          return `${time}<br/>${rows}`
        }
  }

  return (
    <ReactECharts
      option={{ ...base, tooltip, yAxis: { ...base.yAxis, axisLabel: { ...(base.yAxis as { axisLabel: object }).axisLabel, formatter: (v: number) => formatW(v) } }, series }}
      style={{ height, width: '100%' }}
      notMerge
      onChartReady={connectChart}
    />
  )
}
