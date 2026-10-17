import assert from 'node:assert/strict'
import test from 'node:test'
import {
  indexCatalog,
  delta,
  metricDifferences,
  csv,
} from '../src/study/model.ts'
import {
  parseTrajectory,
  reducePoints,
  timestamp,
  fieldLabel,
  unitFor,
} from '../src/study/trajectory.ts'

function entry(key, unit = 'EUR', value = 100, assumptions = {}) {
  return {
    key,
    source: 'study.json',
    trajectory: null,
    record: {
      format: 'vessim.experiment',
      schema_version: 1,
      run_id: key,
      parameters: { capacity: 1000, seed: 42, nested: { x: 1 } },
      config: { microgrids: {} },
      execution: { status: 'completed' },
      metrics: {
        run: { cost: value, missing: null },
        microgrids: { site: { cost: 2 } },
        actors: { site: { load: { cost: 3 } } },
      },
      metric_definitions: {
        run: { cost: { unit, assumptions }, missing: { unit: '1' } },
        microgrids: { site: { cost: { unit } } },
        actors: { site: { load: { cost: { unit } } } },
      },
    },
  }
}
const catalog = (...runs) => indexCatalog({ name: 'test', runs, errors: [] })
test('scopes, nulls and conflicting units survive indexing', () => {
  const data = catalog(entry('a'), entry('b', 'USD'))
  assert.equal(data.columns.filter((c) => c.label === 'cost').length, 6)
  assert.equal(
    data.runs[0].values[data.columns.find((c) => c.label === 'missing').id],
    null,
  )
  assert.equal(data.columns.filter((c) => c.kind === 'parameter').length, 3)
})
test('baseline deltas use units, flag differing metadata, and handle zero', () => {
  const data = catalog(
    entry('base', 'EUR', 0),
    entry('other', 'EUR', 10),
    entry('different', 'EUR', 10, { lifetime: 20 }),
  )
  const col = data.columns.find((c) => c.label === 'cost' && c.scope === 'Run')
  assert.deepEqual(delta(data.runs[1], data.runs[0], col), {
    absolute: 10,
    percent: null,
  })
  assert.deepEqual(delta(data.runs[2], data.runs[0], col), {
    absolute: 10,
    percent: null,
  })
  assert.deepEqual(metricDifferences(data.runs[2], data.runs[0], col), [
    'Assumptions differ',
  ])
  data.runs[2].definitions[col.id].description = 'Clarified wording'
  assert.deepEqual(metricDifferences(data.runs[2], data.runs[0], col), [
    'Description differs',
    'Assumptions differ',
  ])
  assert.notEqual(delta(data.runs[2], data.runs[0], col), null)
  const incompatible = catalog(entry('eur'), entry('usd', 'USD'))
  const euro = incompatible.columns.find(
    (c) => c.scope === 'Run' && c.unit === 'EUR',
  )
  assert.equal(delta(incompatible.runs[1], incompatible.runs[0], euro), null)
})
test('export preserves missing values and escapes spreadsheet formulas and quotes', () => {
  const data = catalog(entry('=bad,"formula"'))
  const result = csv(
    data.runs,
    data.columns.filter((c) => c.label === 'missing'),
  )
  assert.match(result, /'\=bad,""formula""/)
  assert.match(result, /,""$/)
})
test('malformed experiments are isolated', () => {
  const bad = entry('bad')
  bad.record.schema_version = 99
  const data = catalog(bad, entry('good'))
  assert.equal(data.runs.length, 1)
  assert.equal(data.errors.length, 1)
})
test('CSV preserves custom numeric signals and missing observations', () => {
  const parsed = parseTrajectory(
    'microgrid,time,p_grid,actor_states.load.temperature\nsite,2026-01-01 00:00:00,-20,42\nsite,2026-01-01 00:01:00,,43\n',
  )
  assert.equal(
    parsed.series.find((s) => s.field === 'p_grid').points[1][1],
    null,
  )
  assert.equal(
    parsed.series.find((s) => s.field.includes('temperature')).unit,
    'unknown',
  )
  assert.equal(
    timestamp('2026-01-01 00:00:00'),
    Date.parse('2026-01-01T00:00:00Z'),
  )
})
test('large recordings retain peaks, gaps and endpoints with bounded output', () => {
  const points = Array.from({ length: 100000 }, (_, i) => [
    i,
    i === 50001 ? 999999 : i % 23,
  ])
  points[80000][1] = null
  const reduced = reducePoints(points)
  assert.ok(reduced.length <= 4000)
  assert.deepEqual(reduced[0], points[0])
  assert.deepEqual(reduced.at(-1), points.at(-1))
  assert.ok(reduced.some((p) => p[1] === 999999))
  assert.ok(reduced.some((p) => p[1] === null))
})

test('CSV ISO timestamps converted by PapaParse remain valid and timezone-aware', () => {
  const parsed = parseTrajectory(
    'microgrid,time,p_grid\nsite,2026-01-01T01:00:00+01:00,-20\n',
  )
  assert.equal(parsed.rows, 1)
  assert.equal(
    parsed.series[0].points[0][0],
    Date.parse('2026-01-01T00:00:00Z'),
  )
  assert.equal(timestamp('2026-01-01'), Date.parse('2026-01-01T00:00:00Z'))
})

for (const name of ['123', 'true', 'NA', '001', 'false']) {
  test(`CSV preserves microgrid identifier ${name}`, () => {
    const result = parseTrajectory(
      `microgrid,time,p_grid\n${name},2026-01-01,-100\n`,
    )
    assert.equal(result.rows, 1)
    assert.deepEqual(result.warnings, [])
    assert.equal(result.series[0].grid, name)
    assert.equal(result.series[0].points[0][1], -100)
  })
}
test('escaped field paths remain distinct and have readable labels', () => {
  const result = parseTrajectory(
    'microgrid,time,actor_states.a%2Eb.power,actor_states.a.b.power,actor_states.a.literal%252Ekey\nsite,2026-01-01,-100,7,4\n',
  )
  assert.equal(result.series.length, 3)
  assert.equal(fieldLabel(result.series[0].field), 'actor_states / a.b / power')
  assert.equal(
    fieldLabel(result.series[1].field),
    'actor_states / a / b / power',
  )
  assert.equal(
    fieldLabel(result.series[2].field),
    'actor_states / a / literal%2Ekey',
  )
  assert.equal(unitFor('actor_states.a%2Eb.power'), 'W')
  assert.equal(unitFor('dispatch_states.grid.current_power'), 'W')
  assert.equal(unitFor('actor_states.a.b.power'), 'unknown')
  assert.equal(unitFor('actor_states.a.temperature%2Esoc'), 'unknown')
})
