import assert from 'node:assert/strict'
import { test } from 'node:test'
import { indexStudy, completedStudy, columnGroups, signalGroups, visibleSignals, sample, cell } from '../src/model.js'
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
    run_parameters: ['seed'],
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
test('thin indexes derive shared inputs and run identity from records, with optional names', () => {
  const a = record('1', 4), b = record('2', 8)
  const raw = {
    study_id: 'study', run_parameters: ['seed'],
    configurations: [{ configuration_id: 'setup', runs: [{ record: a }, { record: b }] }],
  }
  const study = indexStudy(raw)
  assert.equal(study.name, 'study')
  assert.equal(study.configurations[0].name, 'setup')
  assert.deepEqual(study.runs.map(r => r.key), ['1', '2'])
  const size = study.columns.find(c => c.label === 'size')
  const seed = study.columns.find(c => c.label === 'seed')
  assert.equal(cell(study.configurations[0], size), 10)
  assert.equal(cell(study.configurations[0], seed), null)
  assert.equal(seed.configurationInput, false)
  assert.equal(cell(study.runs[1], seed), 2)
  assert.equal(raw.configurations[0].parameters, undefined)
  b.parameters.size = 20
  const varied = indexStudy(raw)
  assert.equal(cell(varied.configurations[0], size), null)
  assert.equal(varied.configurations.length, 1) // Never infer or change membership.
  b.run_id = '1'
  assert.throws(() => indexStudy(raw), /more than once/)
})
test('configuration display values come from recorded inputs', () => {
  const r = record('1', 4)
  r.parameters.size = 20
  const study = fixture([r])
  const size = study.columns.find(c => c.label === 'size')
  assert.equal(cell(study.configurations[0], size), 20)
})
test('indexed runs keep explicit configuration membership and order', () => {
  const study = indexStudy({configurations: [
    {configuration_id: 'a', runs: [{record: record('3', 7)}, {record: record('1', 4)}]},
    {configuration_id: 'b', runs: [{record: record('2', 8)}]},
  ]})
  assert.deepEqual(study.configurations.map(c => c.runs.map(r => r.key)), [['3', '1'], ['2']])
  assert.equal(study.configurations[0].runs[1], study.runs[1])
  assert.equal(study.runs[2].configuration, study.configurations[1])
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
    'Configuration inputs', 'Whole-system results',
    'Microgrid results · site', 'Actor results · site · solar',
    'Actor results · other · solar', 'Simulation settings',
  ])
  assert.deepEqual(groups[0].columns.map(c => c.label), ['size'])
  assert.deepEqual(groups.at(-1).columns.map(c => c.label), ['seed'])
  assert.equal(groups.flatMap(g => g.columns).length, study.columns.length)
  assert.equal(columnGroups(study.columns.filter(c => c.kind === 'metric')).length, 4)
})
test('single-microgrid labels simplify presentation without changing scoped metric identities', () => {
  const r = record('1', 4)
  r.metrics.microgrids = { campus: { custom: 2 } }
  r.metrics.actors = { campus: { solar: { custom: 3 } } }
  const study = fixture([r])
  assert.equal(study.singleMicrogrid, true)
  assert.deepEqual(study.microgrids, ['campus'])
  const groups = columnGroups(study.columns, study.singleMicrogrid)
  assert.deepEqual(groups.slice(1, -1).map(g => g.label), ['Other results', 'Actor results · solar'])
  assert.deepEqual(groups.flatMap(g => g.columns.map(c => c.id)).sort(), study.columns.map(c => c.id).sort())
  r.metrics.microgrids.other = { custom: 9 }
  const multi = fixture([r])
  assert.equal(multi.singleMicrogrid, false)
  assert.ok(columnGroups(multi.columns, multi.singleMicrogrid).some(g => g.label === 'Microgrid results · other'))
  const ids = multi.columns.filter(c => c.label === 'custom').map(c => c.id)
  assert.equal(new Set(ids).size, 4)
})
test('fixed seeds are settings while sampled seeds stay run inputs', () => {
  const a = record('1', 4), b = record('2', 8)
  a.parameters.seed = b.parameters.seed = 42
  const seedGroup = study => columnGroups(study.columns).find(g => g.columns.some(c => c.label === 'seed')).label
  assert.equal(seedGroup(fixture([a, b])), 'Simulation settings')
  b.parameters.seed = 43
  assert.equal(seedGroup(fixture([a, b])), 'Run inputs')
})
test('single microgrids combine scopes by energy, cost, carbon, with arbitrary results retained', () => {
  const r = record('1', 4)
  r.metrics.run = { annual_cost: 8, initial_embodied_emissions: 9, custom: 2 }
  r.metrics.microgrids = { campus: { grid_emissions: 3, export_revenue: 4, energy_produced: 5 } }
  r.metric_definitions.microgrids = { campus: {} }
  const study = fixture([r])
  const results = columnGroups(study.columns, true).filter(g => g.columns[0].kind === 'metric')
  assert.deepEqual(results.map(g => g.label), ['Energy', 'Cost', 'Carbon', 'Other results'])
  assert.deepEqual(results[1].columns.map(c => c.label), ['annual cost', 'export revenue'])
  assert.deepEqual(results[2].columns.map(c => c.label), ['grid emissions', 'initial embodied emissions'])
  assert.deepEqual(results[1].columns.map(c => c.metricPath), [['run'], ['microgrids', 'campus']])
  assert.equal(results.flatMap(g => g.columns).length, 6)
  r.metrics.microgrids.other = { electricity_cost: 3 }
  const multi = fixture([r])
  assert.deepEqual(columnGroups(multi.columns, multi.singleMicrogrid).filter(g => g.columns[0].kind === 'metric').map(g => g.label),
    ['Whole-system results', 'Microgrid results · campus', 'Microgrid results · other'])
})
test('signal groups keep sites and recorded namespaces separate, including custom fields', () => {
  const signals = [
    { id: 'a', grid: 'west', field: 'actor_states.solar.power' },
    { id: 'b', grid: 'east', field: 'actor_states.solar.power' },
    { id: 'c', grid: 'west', field: 'p_grid' },
    { id: 'd', grid: 'west', field: 'dispatch_states.battery.soc' },
    { id: 'e', grid: 'west', field: 'policy_state.target' },
    { id: 'f', grid: 'west', field: 'grid_signals.carbon' },
    { id: 'g', grid: 'west', field: 'custom.temperature' },
    { id: 'h', grid: 'west', field: 'p_delta' },
  ]
  const sites = signalGroups(signals)
  assert.deepEqual(sites.map(s => s.site), ['east', 'west'])
  assert.deepEqual(sites[1].groups.map(g => g.label), [
    'Dispatchables', 'Actors', 'Grid inputs', 'Policy', 'Other signals',
  ])
  assert.deepEqual(sites[0].groups[0].signals.map(s => s.id), ['b'])
  assert.equal(sites[1].groups.find(g => g.label === 'Actors').signals[0].field, 'p_delta')
  assert.equal(sites.flatMap(s => s.groups.flatMap(g => g.signals)).length, signals.length)
})
test('grid totals are hidden only with an identified and recorded single-connection replacement in every run', () => {
  const signals = [
    {id: 'total', grid: 'site', field: 'p_grid'},
    {id: 'grid', grid: 'site', field: 'dispatch_states.grid.current_power'},
  ]
  const config = {microgrids: {site: {dispatchables: [{name: 'grid', type: 'GridConnection'}]}}}
  const recording = {config, series: signals}
  assert.deepEqual(visibleSignals(signals, [recording]).map(s => [s.id, s.gridPower]), [['grid', true]])
  assert.equal(visibleSignals(signals, [{series: signals}]).length, 2)
  assert.equal(visibleSignals(signals, [recording, {config, series: [signals[0]]}]).length, 2)
  const multiple = structuredClone(config)
  multiple.microgrids.site.dispatchables.push({name: 'other', type: 'GridConnection'})
  assert.equal(visibleSignals(signals, [{config: multiple, series: signals}]).length, 2)
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
