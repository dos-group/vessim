import test from 'node:test'
import assert from 'node:assert/strict'
import { completedStudy, metricCategory } from '../src/model.js'
import { initState } from '../src/state.js'

function fixture(id = 'user-study', reverse = false) {
  const entries = (value) =>
    Object.fromEntries(
      reverse ? Object.entries(value).reverse() : Object.entries(value),
    )
  return completedStudy({
    study_id: id,
    run_parameters: ['seed'],
    configurations: [1, 2, 3].map((size) => ({
      configuration_id: `design-${size}`,
      runs: [42, 43].map((seed) => ({
        record: {
          run_id: `${size}-${seed}`,
          parameters: entries({
            size,
            seed,
            climate: 'temperate',
            model_version: 7,
          }),
          execution: { status: 'completed', simulated_duration: 3600 },
          metrics: {
            run: entries({
              demand: 100,
              missing: null,
              score: size * 5,
              footprint: size * 8,
              consumed: size * 10,
            }),
            microgrids: {},
            actors: {},
          },
          metric_definitions: {
            run: {
              demand: { unit: 'Wh' },
              missing: { unit: 'Wh' },
              score: { unit: 'EUR' },
              footprint: { unit: 'kgCO2e' },
              consumed: { unit: 'Wh' },
            },
            microgrids: {},
            actors: {},
          },
        },
      })),
    })),
  })
}
test('defaults are unchanged by study IDs, labels or JSON field order', () => {
  const reference = initState(fixture())
  for (const id of ['optuna-search', 'infrastructure-arbitrary', 'renamed']) {
    const state = initState(fixture(id, true))
    assert.deepEqual(state.visible, reference.visible)
    assert.equal(state.x, reference.x)
    assert.equal(state.y, reference.y)
  }
})
test('defaults show varying design inputs and diverse measured outcomes', () => {
  const study = fixture(),
    state = initState(study)
  const visible = state.visible.map((id) =>
    study.columns.find((c) => c.id === id),
  )
  assert.deepEqual(
    visible.filter((c) => c.kind === 'parameter').map((c) => c.label),
    ['size'],
  )
  const metrics = visible.filter((c) => c.kind === 'metric')
  assert.deepEqual(metrics.map(metricCategory), ['Energy', 'Cost', 'Carbon'])
  assert.ok(metrics.every((c) => !['missing', 'demand'].includes(c.label)))
  assert.equal(state.x, metrics[0].id)
  assert.equal(state.y, metrics[1].id)
})
test('single-run examples show available metrics and select their recording', () => {
  const study = fixture()
  const single = completedStudy({
    configurations: [
      {
        configuration_id: 'only',
        runs: [{ record: study.runs[0].record }],
      },
    ],
  })
  const state = initState(single)
  assert.equal(state.runs.size, 1)
  assert.deepEqual([...state.timeConfigs], ['only'])
  assert.ok(state.visible.length > 0)
  assert.ok(
    state.visible.every(
      (id) => single.columns.find((c) => c.id === id).kind === 'metric',
    ),
  )
  assert.ok(!state.visible.some((id) => id.includes('missing')))
})
test('whole-system metrics take precedence over site and actor metrics', () => {
  const raw = fixture()
  for (const run of raw.runs) {
    run.record.metrics.microgrids = { north: { a: 1 }, south: { a: 2 } }
    run.record.metric_definitions.microgrids = {
      north: { a: { unit: 'EUR' } },
      south: { a: { unit: 'EUR' } },
    }
  }
  const study = completedStudy(raw)
  const state = initState(study)
  assert.ok(
    state.visible
      .filter((id) => id.startsWith('m:'))
      .every((id) => study.columns.find((c) => c.id === id).scope === 'Run'),
  )
})
