import { useRef } from 'react'
import { move, toggle } from '../state.js'
import { useViewer } from '../context.jsx'

// The same pointer and keyboard behavior is used for table columns and overlays.
export function Reorderable({
  as: Tag = 'li',
  kind,
  itemKey,
  children,
  className = '',
  ...props
}) {
  const { view, patch } = useViewer(),
    drag = useRef(null),
    suppressClick = useRef(false)
  function reorder(target) {
    const position = [...view[kind]].indexOf(target)
    patch((s) => ({ [kind]: move(s[kind], itemKey, position) }))
  }
  function finish(event) {
    if (!drag.current) return
    const start = drag.current
    drag.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId)
    if (Math.hypot(event.clientX - start.x, event.clientY - start.y) < 6) return
    suppressClick.current = true
    const target = document
      .elementFromPoint(event.clientX, event.clientY)
      ?.closest('[data-order-key]')
    if (target?.dataset.kind === kind) reorder(target.dataset.orderKey)
  }
  return (
    <Tag
      {...props}
      className={className}
      data-kind={kind}
      data-order-key={itemKey}
      tabIndex={kind === 'visible' ? undefined : 0}
      onClickCapture={(event) => {
        if (suppressClick.current) {
          event.preventDefault()
          event.stopPropagation()
          suppressClick.current = false
        }
      }}
      onPointerDown={(event) => {
        suppressClick.current = false
        if (
          event.button ||
          event.target.closest('input') ||
          (kind !== 'visible' && event.target.closest('button'))
        )
          return
        drag.current = { x: event.clientX, y: event.clientY }
      }}
      onPointerMove={(event) => {
        if (
          drag.current &&
          Math.hypot(
            event.clientX - drag.current.x,
            event.clientY - drag.current.y,
          ) >= 6
        )
          event.currentTarget.setPointerCapture(event.pointerId)
      }}
      onPointerUp={finish}
      onPointerCancel={() => {
        drag.current = null
      }}
      onKeyDown={(event) => {
        if (
          event.target.closest('input') ||
          (kind === 'visible' ? !event.altKey : event.target.closest('button'))
        )
          return
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return
        event.preventDefault()
        const order = [...view[kind]],
          target =
            order[order.indexOf(itemKey) + (event.key === 'ArrowLeft' ? -1 : 1)]
        if (target) reorder(target)
      }}
    >
      {children}
    </Tag>
  )
}
export function SelectionOrder({ entries, kind }) {
  const { study, view, patch } = useViewer()
  if (!entries.length || entries.length > 8) return null
  const isRun = kind === 'runs'
  return (
    <section
      className="selection-order"
      aria-label={`${isRun ? 'Run' : 'Configuration'} order`}
    >
      <ol>
        {entries.map((entry) => {
          const palette =
            isRun && study.singleRun ? 'runColors' : 'configColors'
          const key =
            isRun && !study.singleRun ? entry.configuration.key : entry.key
          return (
            <Reorderable
              key={entry.key}
              kind={kind}
              itemKey={entry.key}
              title="Drag or use arrow keys to reorder"
              aria-label={`${entry.name}. Drag or use arrow keys to reorder.`}
            >
              <input
                type="color"
                className="run-color"
                value={view[palette][key]}
                aria-label={`Color for ${entry.name}`}
                onChange={(e) =>
                  patch((s) => ({
                    [palette]: { ...s[palette], [key]: e.target.value },
                  }))
                }
              />
              <span className="order-name">{entry.name}</span>
              <button
                aria-label={`Remove ${entry.name}`}
                onClick={() =>
                  patch((s) => ({ [kind]: toggle(s[kind], entry.key, false) }))
                }
              >
                ×
              </button>
            </Reorderable>
          )
        })}
      </ol>
    </section>
  )
}
