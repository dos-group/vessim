import { parseConfig, parseTimeseries, deriveConfigs } from './parser'
import type { MicrogridConfig, MicrogridState } from '../api/types'
import type { ExperimentMetadata } from './parser'

export interface LoadedExperiment {
  metadata: ExperimentMetadata
  timeseriesByMicrogrid: Record<string, MicrogridState[]>
  configByMicrogrid: Record<string, MicrogridConfig>
}

export interface ExperimentEntry {
  name: string  // "" for single-experiment dirs, folder name for multi
  status: 'running' | 'completed' | null
}

export interface ExperimentsResponse {
  mode: 'single' | 'multi'
  experiments: ExperimentEntry[]
}

// When VITE_STATIC_BASE is set (e.g. "/viewer/"), the app fetches data from static
// files relative to that base — suitable for embedding in a documentation site.
// Without it, the dev-server and `vessim view` endpoints (/experiments, /results/*) are used.
const STATIC_BASE: string | undefined = import.meta.env.VITE_STATIC_BASE

export async function fetchExperiments(): Promise<ExperimentsResponse> {
  const url = STATIC_BASE ? `${STATIC_BASE}experiments.json` : '/experiments'
  const res = await fetch(url)
  if (!res.ok) throw new Error('Could not reach the experiments endpoint. Start the viewer with VITE_RESULTS_DIR=/path npm run dev or vessim view /path.')
  return res.json()
}

export async function loadExperiment(name: string): Promise<LoadedExperiment> {
  const prefix = STATIC_BASE
    ? name ? `${STATIC_BASE}results/${name}` : `${STATIC_BASE}results`
    : name ? `/results/${name}` : '/results'
  const [yamlRes, csvRes] = await Promise.all([
    fetch(`${prefix}/metadata.yaml`),
    fetch(`${prefix}/timeseries.csv`),
  ])
  if (!yamlRes.ok) throw new Error(`Could not load metadata.yaml${name ? ` for "${name}"` : ''}`)
  if (!csvRes.ok) throw new Error(`Could not load timeseries.csv${name ? ` for "${name}"` : ''}`)
  const [yamlText, csvText] = await Promise.all([yamlRes.text(), csvRes.text()])
  const metadata = parseConfig(yamlText)
  const timeseriesByMicrogrid = parseTimeseries(csvText, metadata)
  const configByMicrogrid = deriveConfigs(metadata)
  return { metadata, timeseriesByMicrogrid, configByMicrogrid }
}
