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
import { CHART_HEIGHT, CHART_MARGIN, COLORS, formatTime, computeTicks, getTickStyle, getTooltipStyle, getGridColor } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

export function SocChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()

  // Collect all dispatchable names that have SoC
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

  const data = history.map((s) => {
    const point: Record<string, number | string | null> = { time: s.time }
    dispatchNames.forEach((name) => {
      const soc = s.dispatch_states?.[name]?.soc
      point[name] = soc != null ? soc * 100 : null
    })
    return point
  })

  const ticks = computeTicks(history.map((s) => s.time))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={CHART_MARGIN}>
        <defs>
          {dispatchNames.map((name, i) => (
            <linearGradient key={name} id={`socGradient-${name}`} x1="0" y1="0" x2="0" y2="1">
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
          domain={[0, 100]}
          tickFormatter={(v) => `${v}%`}
          tick={getTickStyle(isDark)}
          axisLine={false}
          tickLine={false}
          width={44}
        />
        <Tooltip
          formatter={(v, name) => [`${(v as number).toFixed(1)}%`, `${name} SoC`]}
          labelFormatter={(l) => formatTime(String(l))}
          contentStyle={getTooltipStyle(isDark)}
        />
        <ReferenceLine y={20} stroke="#fbbf24" strokeDasharray="4 2" strokeOpacity={isDark ? 0.5 : 1} />
        {dispatchNames.map((name, i) => (
          <Area
            key={name}
            type="monotone"
            dataKey={name}
            stroke={COLORS[i % COLORS.length]}
            fill={`url(#socGradient-${name})`}
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
