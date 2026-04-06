import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import type { MicrogridState } from '../../api/types'
import { CHART_HEIGHT, CHART_MARGIN, COLORS, formatTime, formatW, computeTicks, getTickStyle, getTooltipStyle, getGridColor } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  mode: 'producers' | 'consumers'
  height?: number
}

export function ActorsChart({ history, mode, height = CHART_HEIGHT }: Props) {
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

  const data = history.map((s) => {
    const point: Record<string, number | string> = { time: s.time }
    actorNames.forEach((name) => {
      const p = s.actor_states[name]?.power ?? 0
      point[name] = Math.abs(p)
    })
    return point
  })

  const ticks = computeTicks(history.map((s) => s.time))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={CHART_MARGIN}>
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
          formatter={(v, name) => [formatW(v as number), name]}
          labelFormatter={(l) => formatTime(String(l))}
          contentStyle={getTooltipStyle(isDark)}
        />
        {actorNames.map((name, i) => (
          <Area
            key={name}
            type="monotone"
            dataKey={name}
            stackId="1"
            stroke={COLORS[i % COLORS.length]}
            fill={COLORS[i % COLORS.length]}
            fillOpacity={isDark ? 0.2 : 0.15}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}
