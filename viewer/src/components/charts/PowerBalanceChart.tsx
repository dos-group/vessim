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
import { CHART_HEIGHT, CHART_MARGIN, formatTime, formatW, computeTicks, getTickStyle, getTooltipStyle, getGridColor, getRefLineColor } from './shared'
import { useTheme } from '../../ThemeContext'

interface Props {
  history: MicrogridState[]
  height?: number
}

export function PowerBalanceChart({ history, height = CHART_HEIGHT }: Props) {
  const { isDark } = useTheme()
  const data = history.map((s) => ({ time: s.time, value: s.p_delta }))
  const ticks = computeTicks(history.map((s) => s.time))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={CHART_MARGIN}>
        <defs>
          <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10b981" stopOpacity={isDark ? 0.3 : 0.2} />
            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
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
          formatter={(v) => [formatW(v as number), 'Power Balance']}
          labelFormatter={(l) => formatTime(String(l))}
          contentStyle={getTooltipStyle(isDark)}
        />
        <ReferenceLine y={0} stroke={getRefLineColor(isDark)} strokeDasharray="4 2" />
        <Area
          type="monotone"
          dataKey="value"
          stroke="#10b981"
          fill="url(#balanceGradient)"
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
