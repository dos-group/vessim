export const CHART_HEIGHT = 180

export const CHART_MARGIN = { top: 4, right: 16, bottom: 4, left: 48 }

export const COLORS = [
  '#3b82f6', // blue-500
  '#10b981', // emerald-500
  '#f59e0b', // amber-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#06b6d4', // cyan-500
  '#f97316', // orange-500
]

export const TICK_STYLE = {
  fontSize: 10,
  fill: '#9ca3af',
  fontFamily: 'ui-monospace, SFMono-Regular, monospace',
}

export const TOOLTIP_STYLE = {
  fontSize: 12,
  borderRadius: 4,
  border: '1px solid #e5e7eb',
  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
}

export function getTickStyle(isDark: boolean) {
  return { ...TICK_STYLE, fill: isDark ? '#6b7280' : '#9ca3af' }
}

export function getTooltipStyle(isDark: boolean) {
  return {
    ...TOOLTIP_STYLE,
    border: `1px solid ${isDark ? '#2d3348' : '#e5e7eb'}`,
    backgroundColor: isDark ? '#1a1d2e' : '#ffffff',
    color: isDark ? '#e2e8f0' : '#111827',
  }
}

export function getGridColor(isDark: boolean) {
  return isDark ? '#1e2130' : '#f3f4f6'
}

export function getRefLineColor(isDark: boolean) {
  return isDark ? '#374151' : '#d1d5db'
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatW(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)} kW`
  return `${value.toFixed(0)} W`
}

export function computeTicks(times: string[], count = 5): string[] {
  if (times.length <= count + 1) return times
  const step = Math.ceil(times.length / count)
  return times.filter((_, i) => i % step === 0)
}
