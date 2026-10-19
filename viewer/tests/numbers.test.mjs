import { test } from 'node:test'
import assert from 'node:assert/strict'
import { columnNumberFormat, formatNumber } from '../src/numbers.js'

test('column precision aligns whole and fractional values while preserving integer inputs', () => {
  const options = columnNumberFormat(1200)
  assert.deepEqual([1200, 2.5, 0].map(v => formatNumber(v, options)), ['1,200.00', '2.50', '0.00'])
  assert.equal(formatNumber(1200, columnNumberFormat(1200, true)), '1,200')
})
test('missing and tiny nonzero values remain distinct from zero', () => {
  const options = columnNumberFormat(10)
  assert.equal(formatNumber(null, options), '—')
  assert.equal(formatNumber(NaN, options), '—')
  assert.equal(formatNumber(-0, options), '0.00')
  assert.equal(formatNumber(0.00001, options), '<0.01')
  assert.equal(formatNumber(-0.00001, options), '>−0.01')
  assert.equal(formatNumber(0.00001, columnNumberFormat(0.00001)), '0.0000100')
  assert.equal(formatNumber(1e-12, columnNumberFormat(1e-12)), '1.00E-12')
})
