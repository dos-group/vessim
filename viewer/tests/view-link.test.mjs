import test from 'node:test'
import assert from 'node:assert/strict'
import { readViewLink, writeViewLink } from '../src/view-link.js'
const study = {
  singleRun: false,
  runs: [{ key: 'run / α' }],
  configurations: [{ key: 'config-2' }, { key: 'config-10' }],
  columns: [{ id: 'metric:energy', unit: 'Wh' }],
}
const defaults = {
  mode: 'configurations',
  timeMode: 'configurations',
  plotType: 'scatter',
  stat: 'median',
  timeStat: 'median',
  spread: 'range',
  timeSpread: 'range',
  alignment: 'elapsed',
  paretoX: 'min',
  paretoY: 'min',
  plot: true,
  plotIndividuals: true,
  timeIndividuals: false,
  pareto: false,
  descending: false,
  selectedFirst: false,
  runs: new Set(),
  configs: new Set(),
  timeConfigs: new Set(),
  configFilter: [],
  visible: ['metric:energy'],
  query: '',
  x: 'metric:energy',
  y: 'metric:energy',
  sort: 'name',
  signals: null,
  units: {},
  signalUnits: {},
  zoom: { start: 0, end: 100 },
}
test('shared views round-trip stable IDs, ordering, Unicode and display preferences under a URL prefix', () => {
  const state = {
    ...defaults,
    mode: 'runs',
    runs: new Set(['run / α']),
    configs: new Set(['config-10', 'config-2']),
    units: { 'metric:energy': 'kWh' },
    signals: ['["site","p_grid"]'],
    zoom: { start: 15, end: 70 },
    query: 'summer & winter',
  }
  const url = new URL(
    writeViewLink(
      'https://example.org/docs/en/latest/viewer/?study=old#results',
      'new-study',
      'timeseries',
      state,
      defaults,
    ),
  )
  assert.equal(url.pathname, '/docs/en/latest/viewer/')
  assert.equal(url.hash, '#timeseries')
  assert.equal(url.searchParams.get('study'), 'new-study')
  assert.deepEqual(
    readViewLink(url.searchParams.get('view'), defaults, study),
    state,
  )
  assert.equal(JSON.parse(url.searchParams.get('view')).plotType, undefined)
  assert.equal(
    new URL(
      writeViewLink(url.href, 'new-study', 'results', defaults, defaults),
    ).searchParams.has('view'),
    false,
  )
})
test('existing v1 links remain readable and tolerate deleted fields and runs', () => {
  const old =
    '{"v":1,"mode":"runs","runs":["deleted","run / α"],"configs":["deleted"],"visible":["deleted"],"x":"deleted","futureOption":true,"zoom":{"start":10,"end":90}}'
  const result = readViewLink(old, defaults, study)
  assert.deepEqual([...result.runs], ['run / α'])
  assert.deepEqual(result.visible, defaults.visible)
  assert.equal(result.x, defaults.x)
  assert.equal(result.futureOption, undefined)
  assert.deepEqual(result.zoom, { start: 10, end: 90 })
  assert.deepEqual(
    readViewLink('{"v":1,"visible":[],"runs":[]}', defaults, study).visible,
    [],
  )
})
test('malformed, future-version, and mistyped payloads fall back without changing defaults', () => {
  for (const raw of [null, '{', '[]', 'null', '{"v":2,"mode":"runs"}'])
    assert.deepEqual(readViewLink(raw, defaults, study), defaults)
  const result = readViewLink(
    '{"v":1,"mode":"oops","runs":{},"units":[],"signals":[42],"plot":"false","zoom":{"start":90,"end":10},"__proto__":{"bad":true}}',
    defaults,
    study,
  )
  assert.deepEqual(result, defaults)
  assert.equal({}.bad, undefined)
})
