import { useEffect } from 'react'
import ReactECharts from 'echarts-for-react/esm/core'
import * as echarts from 'echarts/core'
import { ScatterChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  ToolboxComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import { useTheme } from '../theme'

echarts.use([
  ScatterChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  ToolboxComponent,
  CanvasRenderer,
])
import { colors } from './colors'
export function Chart({
  option,
  height = 330,
  group,
  onPoint,
}: {
  option: EChartsOption
  height?: number
  group?: string
  onPoint?: (key: string) => void
}) {
  const { isDark } = useTheme()
  useEffect(
    () => () => {
      if (group) echarts.disconnect(group)
    },
    [group],
  )
  const text = isDark ? '#a9b7c5' : '#64756f'
  return (
    <ReactECharts
      theme={isDark ? 'dark' : undefined}
      echarts={echarts}
      style={{ height, width: '100%' }}
      notMerge
      onChartReady={(chart) => {
        if (group) {
          chart.group = group
          echarts.connect(group)
        }
      }}
      onEvents={
        onPoint
          ? {
              click: (event: { data?: { runKey?: string } }) => {
                if (event.data?.runKey) onPoint(event.data.runKey)
              },
            }
          : undefined
      }
      option={{
        backgroundColor: 'transparent',
        color: colors,
        animation: false,
        textStyle: { fontFamily: 'inherit', color: text },
        grid: { top: 24, bottom: 56, left: 80, right: 32 },
        tooltip: { trigger: 'axis', renderMode: 'richText', confine: true },
        xAxis: {
          type: 'value',
          axisLabel: { color: text },
          splitLine: { show: false },
        },
        yAxis: {
          type: 'value',
          axisLabel: { color: text },
          splitLine: { lineStyle: { color: isDark ? '#263831' : '#edf0e9' } },
        },
        ...option,
      }}
    />
  )
}
