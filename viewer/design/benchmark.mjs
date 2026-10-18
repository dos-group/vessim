// Isolated indexing benchmark, not a browser or network benchmark.
// Run: node viewer/design/benchmark.mjs [configuration-count]
import { indexStudy } from '../src/model.js'

const count = Number(process.argv[2] || 10000)
if (!Number.isSafeInteger(count) || count < 1) throw Error('Count must be a positive integer')
const fixture = {
  configurations: Array.from({ length: count }, (_, i) => ({
    configuration_id: `c-${i}`,
    runs: [{ record: {
      run_id: `r-${i}`,
      parameters: { size: i, seed: 42 },
      execution: { status: 'completed' },
      metrics: { run: { cost: i * 7, emissions: count - i }, microgrids: {}, actors: {} },
      metric_definitions: {
        run: { cost: { unit: 'EUR' }, emissions: { unit: 'kgCO2e' } },
        microgrids: {}, actors: {},
      },
    } }],
  })),
}
const milliseconds = []
for (let iteration = 0; iteration < 4; iteration++) {
  const start = performance.now()
  const result = indexStudy(fixture)
  milliseconds.push(Math.round(performance.now() - start))
  if (result.runs.length !== count || result.configurations.some(c => c.runs.length !== 1))
    throw Error('Unexpected indexed membership')
}
console.log(JSON.stringify({ configurations: count, runs: count, milliseconds }))
