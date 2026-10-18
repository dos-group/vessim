import { test } from 'node:test'
import assert from 'node:assert/strict'
import { displayUnit, inDisplayUnit, unitOptions } from '../src/units.js'

test('large energy totals use one consistent column scale', () => {
  const spec = displayUnit('Wh', 8.9e9)
  assert.equal(spec.unit, 'GWh')
  assert.equal(inDisplayUnit(8.9e9, spec), 8.9)
  assert.equal(inDisplayUnit(1e8, spec), 0.1)
  assert.equal(inDisplayUnit(null, spec), null)
  assert.equal(inDisplayUnit(0, spec), 0)
})
test('overrides convert from the recorded unit, including negative deltas', () => {
  const spec = displayUnit('kWh', 8.9e6, 'GWh')
  assert.equal(inDisplayUnit(-2e6, spec), -2)
  assert.equal(displayUnit('kgCO2e', 2e6).unit, 'tCO2e')
  assert.equal(displayUnit('W', 3e6).unit, 'MW')
  assert.equal(displayUnit('Wh', 8.9e9, 'kWh').factor, 1000)
})
test('unknown units and dimensionless counts are never guessed', () => {
  assert.deepEqual(unitOptions('widgets'), [{ unit: 'widgets', factor: 1 }])
  assert.equal(displayUnit('widgets', 9e9).unit, 'widgets')
  assert.equal(displayUnit('1', 0.8).unit, '1')
  assert.equal(displayUnit('MWh', 0).unit, 'MWh')
  assert.equal(displayUnit('MWh', NaN).unit, 'MWh')
})
