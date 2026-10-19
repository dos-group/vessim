import assert from 'node:assert/strict'
import { test } from 'node:test'
import { summarize, summarizeTrajectories, empiricalDistribution } from '../src/uncertainty.js'

test('empirical distributions count tied observations together and exclude missing values', () => {
  assert.deepEqual(empiricalDistribution([4, null, -2, 4, 0, NaN, Infinity]), [
    [-2, 0], [-2, 25], [0, 50], [4, 100],
  ])
  assert.deepEqual(empiricalDistribution([0, 0]), [[0, 0], [0, 100]])
  assert.deepEqual(empiricalDistribution([null]), [])
})

test('summaries exclude missing values, retain zeros, and use explicit spread', () => {
  assert.deepEqual(summarize([null, 0, 4, 8, NaN]), {center: 4, low: 0, high: 8, count: 3})
  assert.deepEqual(summarize([1, 2, 3, 10], 'mean', 'iqr'), {center: 4, low: 1.75, high: 4.75, count: 4})
  assert.deepEqual(summarize([null], 'median'), {center: null, low: null, high: null, count: 0})
  assert.deepEqual(summarize([2], 'mean', 'none'), {center: 2, low: null, high: null, count: 1})
})
test('trajectory summaries preserve timestamps, negative ranges and per-time counts', () => {
  const series = [
    {count: 3, points: [[0, -4], [1, null], [2, null]]},
    {count: 3, points: [[0, 2], [1, 8], [2, null]]},
  ]
  assert.deepEqual(summarizeTrajectories(series, 'median', 'range'), [
    {time: 0, center: -1, low: -4, high: 2, count: 2},
    {time: 1, center: 8, low: 8, high: 8, count: 1},
    {time: 2, center: null, low: null, high: null, count: 0},
  ])
})
test('aggregation never silently interpolates or summarizes reduced trajectories', () => {
  const first = {count: 2, points: [[0, 1], [1, 2]]}
  assert.throws(() => summarizeTrajectories([first, {count: 2, points: [[0, 1], [2, 2]]}]), /matching timestamps/)
  assert.throws(() => summarizeTrajectories([first, {count: 1, points: [[0, 1]]}]), /matching timestamps/)
  assert.throws(() => summarizeTrajectories([{...first, count: 100000}]), /reduced recordings/)
})
