import type { MicrogridConfig } from '../api/types'
import { parseConfig, parseTimeseries, deriveConfigs, type ExperimentMetadata } from './parser'
import type { MicrogridState } from '../api/types'

export interface LoadedExperiment {
  metadata: ExperimentMetadata
  timeseriesByMicrogrid: Record<string, MicrogridState[]>
  configByMicrogrid: Record<string, MicrogridConfig>
}

export interface ExperimentSummary {
  name: string
  status: 'running' | 'completed' | undefined
  configFile: File
  csvFile: File | null
}

function buildExperiment(yamlText: string, csvText: string): LoadedExperiment {
  const metadata = parseConfig(yamlText)
  const timeseriesByMicrogrid = parseTimeseries(csvText, metadata)
  const configByMicrogrid = deriveConfigs(metadata)
  return { metadata, timeseriesByMicrogrid, configByMicrogrid }
}

/**
 * Detects whether the selected files represent multiple experiment subdirectories.
 * Returns a list of summaries if so, or null if it's a single experiment directory.
 */
export async function detectExperiments(files: FileList): Promise<ExperimentSummary[] | null> {
  const bySubdir: Record<string, { config?: File; csv?: File }> = {}
  let hasRootConfig = false

  for (const file of files) {
    const parts = file.webkitRelativePath.split('/')
    // parts[0] = selected dir name, parts[1] = subdir or filename, parts[2] = filename in subdir
    if (parts.length === 2) {
      const fname = parts[1].toLowerCase()
      if (fname === 'config.yaml' || fname === 'config.yml') hasRootConfig = true
    } else if (parts.length === 3) {
      const subdir = parts[1]
      const fname = parts[2].toLowerCase()
      if (!bySubdir[subdir]) bySubdir[subdir] = {}
      if (fname === 'config.yaml' || fname === 'config.yml') bySubdir[subdir].config = file
      else if (fname === 'timeseries.csv') bySubdir[subdir].csv = file
    }
  }

  if (hasRootConfig) return null

  const subdirs = Object.entries(bySubdir).filter(([, { config }]) => config != null)
  if (subdirs.length === 0) return null

  const summaries = await Promise.all(
    subdirs.map(async ([name, { config, csv }]) => {
      const yamlText = await config!.text()
      const metadata = parseConfig(yamlText)
      return { name, status: metadata.status, configFile: config!, csvFile: csv ?? null }
    })
  )

  return summaries.sort((a, b) => a.name.localeCompare(b.name))
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

export async function loadFromSummary(summary: ExperimentSummary): Promise<LoadedExperiment> {
  if (!summary.csvFile) {
    throw new Error(`No timeseries.csv found for experiment "${summary.name}"`)
  }
  const [yamlText, csvText] = await Promise.all([
    summary.configFile.text(),
    summary.csvFile.text(),
  ])
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
