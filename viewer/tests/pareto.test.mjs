import assert from 'node:assert/strict'
import { test } from 'node:test'
import { paretoFront } from '../src/pareto.js'

test('Pareto fronts retain ties and handle all objective directions', () => {
  const points = [[0, 4], [0, 5], [1, 3], [1, 3], [2, 3], [2, 2], [4, 0], [5, 0], [-1, 6]]
    .map((value, key) => ({key, value}))
  for (const x of ['min', 'max']) {
    for (const y of ['min', 'max']) {
      const directions = [x, y]
      const expected = points.filter(p => !points.some(q => {
        const difference = q.value.map((v, i) => (v - p.value[i]) * (directions[i] === 'min' ? 1 : -1))
        return difference.every(d => d <= 0) && difference.some(d => d < 0)
      })).map(p => p.key).sort()
      assert.deepEqual(paretoFront(points, x, y).map(p => p.key).sort(), expected)
    }
  }
})

test('Pareto fronts exclude nonfinite values and respond to filtering', () => {
  const first = {key: 'a', value: [0, 0]}, second = {key: 'b', value: [1, 1]}
  assert.deepEqual(paretoFront([second, first, {value: [NaN, 0]}, {value: [0, Infinity]}]), [first])
  assert.deepEqual(paretoFront([second]), [second])
  assert.deepEqual(paretoFront([]), [])
  assert.deepEqual(paretoFront([{value: [0, 2]}, {value: [0, 1]}]), [{value: [0, 1]}])
})
