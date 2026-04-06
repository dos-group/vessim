import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'
import type { MicrogridState } from '../../api/types'
import { CHART_HEIGHT, CHART_MARGIN, COLORS, formatTime, formatW, computeTicks, getTickStyle, getTooltipStyle, getGridColor, getRefLineColor } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

// Derive instantaneous dispatch power (W) from charge_level deltas.
// Positive = charging, negative = discharging.
function buildDispatchData(history: MicrogridState[]) {
  if (history.length < 2) return { names: [] as string[], data: [] as Record<string, number | string>[] }

  const names = Array.from(
    new Set(
      history.flatMap((s) =>
        s.dispatch_states ? Object.keys(s.dispatch_states) : []
      )
    )
  )

  const data = history.map((s, i) => {
    const point: Record<string, number | string> = { time: s.time }
    if (i === 0) {
      names.forEach((n) => { point[n] = 0 })
      return point
    }
    const prev = history[i - 1]
    const dtHours = (new Date(s.time).getTime() - new Date(prev.time).getTime()) / 3_600_000
    names.forEach((n) => {
      const curr = s.dispatch_states?.[n]?.charge_level ?? null
      const prevLevel = prev.dispatch_states?.[n]?.charge_level ?? null
      if (curr === null || prevLevel === null || dtHours === 0) {
        point[n] = 0
      } else {
        point[n] = (curr - prevLevel) / dtHours
      }
    })
    return point
  })

  return { names, data }
}

export function DispatchChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const { names, data } = buildDispatchData(history)
  const ticks = computeTicks(history.map((s) => s.time))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={CHART_MARGIN}>
        <defs>
          {names.map((name, i) => (
            <linearGradient key={name} id={`dispGrad-${name}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={COLORS[i % COLORS.length]} stopOpacity={isDark ? 0.3 : 0.2} />
              <stop offset="95%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={getGridColor(isDark)} />
        <XAxis
          dataKey="time"
          ticks={ticks}
          tickFormatter={formatTime}
          tick={getTickStyle(isDark)}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v) => formatW(v as number)}
          tick={getTickStyle(isDark)}
          axisLine={false}
          tickLine={false}
          width={44}
        />
        <Tooltip
          formatter={(v, name) => [formatW(v as number), String(name)]}
          labelFormatter={(l) => formatTime(String(l))}
          contentStyle={getTooltipStyle(isDark)}
        />
        <ReferenceLine y={0} stroke={getRefLineColor(isDark)} strokeDasharray="4 2" />
        {names.map((name, i) => (
          <Area
            key={name}
            type="monotone"
            dataKey={name}
            stroke={COLORS[i % COLORS.length]}
            fill={`url(#dispGrad-${name})`}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}
