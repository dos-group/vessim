import { test } from 'node:test'
import assert from 'node:assert/strict'
import { trajectoryOptions } from '../src/trajectory.js'

test('trajectory tooltips use automatic units even when the axis unit is overridden', () => {
  const watts = trajectoryOptions([], 'elapsed', {}, { unit: 'W', factor: 1 }, 2e6)
  const kilowatts = trajectoryOptions([], 'elapsed', {}, { unit: 'kW', factor: 1000 }, 2e6)
  assert.equal(watts.tooltip.valueFormatter(1234567.891234), '1.23 MW')
  assert.equal(kilowatts.tooltip.valueFormatter(1234.567891234), '1.23 MW')
  assert.equal(watts.tooltip.valueFormatter(-1234567.891234), '-1.23 MW')
  assert.equal(watts.tooltip.valueFormatter([1234567.89, 1987654.32]), '1.23 MW – 1.99 MW')
})

test('trajectory tooltips preserve fractions, missing values and small nonzero values', () => {
  const fraction = trajectoryOptions([], 'elapsed', {}, { unit: '1', factor: 1 }, 1)
  assert.equal(fraction.tooltip.valueFormatter(0.123456789), '0.12')
  assert.equal(fraction.tooltip.valueFormatter(null), '—')
  assert.equal(fraction.tooltip.valueFormatter(0.00001), '<0.01')
})
