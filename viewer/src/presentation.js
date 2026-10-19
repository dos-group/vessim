import { metricCategory, human } from './model.js'
import { columnNumberFormat, formatNumber } from './numbers.js'
import { displayUnit, inDisplayUnit } from './units.js'
export const fmt = (v) =>
  v == null
    ? '—'
    : typeof v === 'number'
      ? v.toLocaleString('en-GB', { maximumSignificantDigits: 5 })
      : typeof v === 'object'
        ? JSON.stringify(v)
        : String(v)
export const signalLabel = (signal) => {
  if (signal.field === 'p_grid') return 'Total grid power'
  if (signal.field === 'p_delta') return 'Net actor power'
  const parts = signal.field
    .split('.')
    .map((s) => s.replaceAll('%2E', '.').replaceAll('%25', '%'))
  const label =
    {
      soc: 'State of charge',
      charge_level: 'Stored energy',
      power: 'Power',
      current_power: 'Power',
    }[parts.at(-1)] || human(parts.at(-1))
  return parts.length > 1
    ? `${parts.slice(1, -1).join(' / ') || human(parts[0])} / ${label}`
    : label
}

export function presentation(study, s) {
  const field = (id) => study.columns.find((c) => c.id === id)
  const spec = (c) => displayUnit(c.unit, s.magnitudes[c.id], s.units[c.id])
  const unit = (c) => spec(c).unit
  const value = (c, v) => (c.kind === 'metric' ? inDisplayUnit(v, spec(c)) : v)
  const metricText = (c, v) => {
    const converted = value(c, v)
    return typeof converted === 'number'
      ? formatNumber(
          converted,
          columnNumberFormat(
            value(c, s.magnitudes[c.id]),
            c.kind === 'parameter' && s.integerColumns[c.id],
          ),
        )
      : fmt(converted)
  }
  const scopeLabel = (c) => {
    if (!c.metricPath) return c.scope
    if (!study.singleMicrogrid)
      return c.metricPath[0] === 'run' ? 'Whole system' : c.scope
    return c.metricPath[0] === 'actors'
      ? `Actor: ${c.metricPath[2]}`
      : metricCategory(c)
  }
  const columnLabel = (c) =>
    `${scopeLabel(c)} · ${c.label}${unit(c) && unit(c) !== '1' ? ` (${unit(c)})` : ''}`

  return { field, spec, unit, value, metricText, scopeLabel, columnLabel }
}
