import { cell, sample } from './model.js'
import { summarize } from './uncertainty.js'
import { fmt, presentation } from './presentation.js'
import { visibleRows, inSelectionOrder } from './state.js'
export function exportRows(study, current, active) {
  const selected = () => current[current.mode === 'runs' ? 'runs' : 'configs']
  const entities = () =>
    current.mode === 'runs' ? study.runs : study.configurations
  const { field, columnLabel, value } = presentation(study, current)
  const cols = current.visible.map(field).filter(Boolean),
    rows = selected().size
      ? inSelectionOrder(entities(), selected())
      : visibleRows(study, current)
  const escape = (v) => {
    let t = typeof v === 'number' ? String(v) : fmt(v)
    if (v == null) t = ''
    if (typeof v !== 'number' && /^[=+\-@\t\r]/.test(t)) t = "'" + t
    return '"' + t.replaceAll('"', '""') + '"'
  }
  const aggregated = current.mode === 'configurations'
  const exportColumns = cols.flatMap((c) => {
    const columns = [
      {
        label: columnLabel(c),
        read: (e) => value(c, cell(e, c, current.stat)),
      },
    ]
    if (aggregated && c.kind === 'metric') {
      const stats = (e) =>
        summarize(
          sample(e, c).points.map((p) => value(c, p.value)),
          current.stat,
          current.spread,
        )
      if (current.spread !== 'none')
        columns.push(
          {
            label: `${columnLabel(c)} · ${current.spread === 'iqr' ? 'Q25' : 'min'}`,
            read: (e) => stats(e).low,
          },
          {
            label: `${columnLabel(c)} · ${current.spread === 'iqr' ? 'Q75' : 'max'}`,
            read: (e) => stats(e).high,
          },
        )
      columns.push({
        label: `${columnLabel(c)} · contributing runs`,
        read: (e) => stats(e).count,
      })
    }
    return columns
  })
  const lines = [
    ['id', 'configuration', 'summary', ...exportColumns.map((c) => c.label)],
    ...rows.map((e) => [
      e.key,
      e.runs ? e.key : e.configuration.key,
      e.runs ? current.stat : 'recorded',
      ...exportColumns.map((c) => c.read(e)),
    ]),
  ]

  const url = URL.createObjectURL(
      new Blob([lines.map((row) => row.map(escape).join(',')).join('\r\n')], {
        type: 'text/csv',
      }),
    ),
    a = document.createElement('a')
  a.href = url
  a.download = `${active}-${study.singleRun ? 'configurations' : current.mode}.csv`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
