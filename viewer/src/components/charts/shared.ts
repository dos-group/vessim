import type { EChartsOption } from 'echarts'

export const CHART_HEIGHT = 200

export const PRODUCER_COLORS = ['#22c55e', '#16a34a', '#4ade80', '#15803d', '#86efac']
export const CONSUMER_COLORS = ['#ef4444', '#dc2626', '#f87171', '#b91c1c', '#fca5a5']

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatW(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)} kW`
  return `${value.toFixed(0)} W`
}

export function getBaseOption(isDark: boolean): EChartsOption {
  const textColor = isDark ? '#4b5563' : '#9ca3af'
  const gridColor = isDark ? '#1e2130' : '#f3f4f6'

  return {
    animation: false,
    backgroundColor: 'transparent',
    grid: { top: 28, right: 56, bottom: 24, left: 60 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: isDark ? '#1a1d2e' : '#ffffff',
      borderColor: isDark ? '#2d3348' : '#e5e7eb',
      borderWidth: 1,
      textStyle: { color: isDark ? '#e2e8f0' : '#111827', fontSize: 12 },
      extraCssText: 'border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,.12);',
    },
    xAxis: {
      type: 'time',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: gridColor } },
      axisLabel: { color: textColor, fontSize: 10, fontFamily: 'ui-monospace, monospace' },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: gridColor } },
      axisLabel: { color: textColor, fontSize: 10, fontFamily: 'ui-monospace, monospace' },
    },
    toolbox: {
      right: 6,
      top: 4,
      itemSize: 12,
      itemGap: 6,
      iconStyle: { borderColor: textColor, borderWidth: 1.5 },
      emphasis: { iconStyle: { borderColor: isDark ? '#e2e8f0' : '#374151' } },
      feature: {
        dataZoom: { yAxisIndex: 'none', title: { zoom: 'Box zoom', back: 'Reset zoom' } },
        restore: { title: 'Reset' },
        saveAsImage: { title: 'Save as PNG', pixelRatio: 2 },
      },
    },
    dataZoom: [{ type: 'inside', filterMode: 'none' }],
  }
}
