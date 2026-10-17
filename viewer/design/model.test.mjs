import assert from 'node:assert/strict'
import { test } from 'node:test'
import { indexStudy, completedStudy, columnGroups, sample, cell } from './model.js'
const record = (id, value, status = 'completed', unit = 'widgets') => ({
  run_id: id,
  parameters: { size: 10, seed: Number(id) },
  execution: { status, simulated_duration: 60 },
  metrics: { run: { custom: value }, microgrids: {}, actors: {} },
  metric_definitions: {
    run: {
      custom: {
        unit,
        description: 'Custom result',
        assumptions: { window: 60 },
      },
    },
    microgrids: {},
    actors: {},
  },
})
const fixture = (records) =>
  indexStudy({
    configurations: [
      {
        configuration_id: 'c',
        name: 'Candidate',
        parameters: { size: 10 },
        conditions: { duration_s: 60 },
        runs: records.map((record) => ({ run_id: record.run_id, record })),
      },
    ],
  })
test('completed study hides incomplete runs and simplifies only true single-run configurations', () => {
  const raw = { configurations: [
    { configuration_id: 'a', name: 'Setup A', parameters: {}, runs: [
      { run_id: '1', record: record('1', 8) },
      { run_id: '2', record: record('2', 4, 'interrupted') },
    ] },
    { configuration_id: 'b', name: 'Setup B', parameters: {}, runs: [
      { run_id: '3', record: record('3', 4, 'failed') },
    ] },
  ] }
  const study = completedStudy(raw)
  assert.equal(study.configurations.length, 1)
  assert.equal(study.runs.length, 1)
  assert.equal(study.runs[0].name, 'Setup A')
  assert.equal(study.singleRun, true)
  assert.equal(raw.configurations[0].runs.length, 2)
  raw.configurations[0].runs[1].record.execution.status = 'completed'
  assert.equal(completedStudy(raw).singleRun, false)
  assert.equal(completedStudy({ configurations: [] }).singleRun, false)
})
test('arbitrary metrics keep unit and scope; runs expose recorded values', () => {
  const study = fixture([
    record('1', 4),
    record('2', null),
    record('3', 9, 'completed', 'other'),
  ])
  const metrics = study.columns.filter((c) => c.kind === 'metric')
  assert.equal(metrics.length, 2)
  assert.equal(cell(study.runs[0], metrics[0]), 4)
  assert.equal(cell(study.runs[1], metrics[0]), null)
  assert.equal(cell(study.runs[2], metrics[0]), null)
})
test('column groups use explicit configuration membership and metric scope', () => {
  const r = record('1', 4)
  r.metrics.microgrids = { site: { custom: 2 } }
  r.metrics.actors = { site: { solar: { custom: 3 } }, other: { solar: { custom: 5 } } }
  const study = fixture([r])
  const groups = columnGroups(study.columns)
  assert.deepEqual(groups.map(g => g.label), [
    'Configuration inputs', 'Run inputs', 'Run results',
    'Microgrid results · site', 'Actor results · site · solar',
    'Actor results · other · solar',
  ])
  assert.deepEqual(groups[0].columns.map(c => c.label), ['size'])
  assert.deepEqual(groups[1].columns.map(c => c.label), ['seed'])
  assert.equal(groups.flatMap(g => g.columns).length, study.columns.length)
  assert.equal(columnGroups(study.columns.filter(c => c.kind === 'metric')).length, 4)
})
test('explicit summaries exclude failed and missing runs and keep denominators', () => {
  const study = fixture([
    record('1', 2),
    record('2', 8),
    record('3', null),
    record('4', 100, 'failed'),
  ])
  const c = study.configurations[0],
    m = study.columns.find((c) => c.kind === 'metric')
  assert.equal(sample(c, m).excluded, 2)
  assert.equal(cell(c, m, ''), null)
  assert.equal(cell(c, m, 'mean'), 5)
  assert.equal(cell(c, m, 'median'), 5)
  assert.equal(cell(c, m, 'min'), 2)
  assert.equal(cell(c, m, 'max'), 8)
})
test('definitions and horizons cannot be silently pooled', () => {
  const a = record('1', 2),
    b = record('2', 8)
  b.metric_definitions.run.custom.assumptions.window = 30
  let study = fixture([a, b]),
    m = study.columns.find((c) => c.kind === 'metric')
  assert.equal(sample(study.configurations[0], m).reason, 'Definitions differ')
  assert.equal(cell(study.configurations[0], m, 'mean'), null)
  b.metric_definitions.run.custom.assumptions.window = 60
  b.execution.simulated_duration = 30
  study = fixture([a, b])
  m = study.columns.find((c) => c.kind === 'metric')
  assert.match(sample(study.configurations[0], m).reason, /Horizons/)
})
