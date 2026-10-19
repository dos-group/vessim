/* global echarts */
import { useEffect, useRef } from 'react'

// ECharts owns only this canvas. React owns its container and the surrounding UI.
export function Chart({
  option,
  onSelect,
  onZoom,
  group,
  id,
  className = 'scatter',
  label,
}) {
  const element = useRef(null),
    instance = useRef(null),
    callbacks = useRef({ onSelect, onZoom })
  useEffect(() => {
    callbacks.current = { onSelect, onZoom }
  }, [onSelect, onZoom])
  useEffect(() => {
    const chart = echarts.init(element.current)
    instance.current = chart
    if (group) {
      chart.group = group
      echarts.connect(group)
    }
    chart.on('click', (event) => {
      if (event.data?.key) callbacks.current.onSelect?.(event.data.key)
    })
    chart.on('datazoom', () =>
      callbacks.current.onZoom?.(
        chart.getOption().dataZoom.map(({ start, end }) => ({ start, end })),
      ),
    )
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(element.current)
    return () => {
      observer.disconnect()
      chart.dispose()
      instance.current = null
    }
  }, [group])
  useEffect(() => {
    if (option)
      instance.current?.setOption(option, { notMerge: true, silent: true })
  }, [option])
  return <div ref={element} id={id} className={className} aria-label={label} />
}
