import type { MicrogridConfig } from '../api/types'
import { parseConfig, parseTimeseries, deriveConfigs, type ExperimentMetadata } from './parser'
import type { MicrogridState } from '../api/types'

export interface LoadedExperiment {
  metadata: ExperimentMetadata
  timeseriesByMicrogrid: Record<string, MicrogridState[]>
  configByMicrogrid: Record<string, MicrogridConfig>
}

function buildExperiment(yamlText: string, csvText: string): LoadedExperiment {
  const metadata = parseConfig(yamlText)
  const timeseriesByMicrogrid = parseTimeseries(csvText, metadata)
  const configByMicrogrid = deriveConfigs(metadata)
  return { metadata, timeseriesByMicrogrid, configByMicrogrid }
}

export async function loadFromFiles(files: FileList): Promise<LoadedExperiment> {
  let configFile: File | null = null
  let csvFile: File | null = null

  for (const file of files) {
    const name = file.name.toLowerCase()
    if (name === 'config.yaml' || name === 'config.yml') {
      configFile = file
    } else if (name === 'timeseries.csv') {
      csvFile = file
    }
  }

  if (!configFile) {
    throw new Error('No config.yaml found in selected directory')
  }
  if (!csvFile) {
    throw new Error('No timeseries.csv found in selected directory')
  }

  const [yamlText, csvText] = await Promise.all([configFile.text(), csvFile.text()])
  return buildExperiment(yamlText, csvText)
}

export async function loadFromServer(): Promise<LoadedExperiment> {
  const [yamlRes, csvRes] = await Promise.all([
    fetch('/results/config.yaml'),
    fetch('/results/timeseries.csv'),
  ])

  if (!yamlRes.ok || !csvRes.ok) {
    throw new Error('Could not load experiment from server')
  }

  const [yamlText, csvText] = await Promise.all([yamlRes.text(), csvRes.text()])
  return buildExperiment(yamlText, csvText)
}
