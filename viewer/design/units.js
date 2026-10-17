// Display conversions only. Metric identities, definitions, and stored values stay intact.
const families = [
  [
    ['Wh', 1],
    ['kWh', 1e3],
    ['MWh', 1e6],
    ['GWh', 1e9],
    ['TWh', 1e12],
  ],
  [
    ['W', 1],
    ['kW', 1e3],
    ['MW', 1e6],
    ['GW', 1e9],
  ],
  [
    ['gCO2e', 0.001],
    ['kgCO2e', 1],
    ['tCO2e', 1e3],
  ],
]
export function unitOptions(unit) {
  const family = families.find((family) =>
    family.some(([name]) => name === unit),
  )
  if (!family) return [{ unit, factor: 1 }]
  const original = family.find(([name]) => name === unit)[1]
  return family.map(([unit, scale]) => ({ unit, factor: scale / original }))
}
export function displayUnit(unit, magnitude, preference = 'auto') {
  const options = unitOptions(unit)
  if (preference !== 'auto')
    return (
      options.find((o) => o.unit === preference) ||
      options.find((o) => o.unit === unit)
    )
  if (!Number.isFinite(magnitude) || magnitude === 0)
    return options.find((o) => o.unit === unit)
  return options.filter((o) => magnitude / o.factor >= 1).at(-1) || options[0]
}
export function inDisplayUnit(value, spec) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value / spec.factor
    : null
}
