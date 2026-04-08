import type { MicrogridConfig } from '../api/types'
import type { LoadedExperiment } from '../data/fileLoader'
import { MicrogridInfoPanel } from './MicrogridInfoPanel'
import type { MicrogridState } from '../api/types'

interface Props {
  experiment: LoadedExperiment
  onSelectMicrogrid: (name: string) => void
}

function fmtDate(iso: string): string {
  const d = new Date(iso.replace(' ', 'T'))
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
    + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtSimDuration(start: string, end: string): string {
  const hours = (new Date(end.replace(' ', 'T')).getTime() - new Date(start.replace(' ', 'T')).getTime()) / 3_600_000
  return hours >= 24 ? `${(hours / 24).toFixed(1)}d` : `${hours.toFixed(0)}h`
}

function fmtRuntime(sec: number): string {
  if (sec < 1) return `${(sec * 1000).toFixed(0)}ms`
  if (sec < 60) return `${sec.toFixed(1)}s`
  return `${(sec / 60).toFixed(1)}min`
}

function MicrogridCard({
  name, history, config, stepSize, onSelect,
}: {
  name: string
  history: MicrogridState[]
  config: MicrogridConfig
  stepSize: number
  onSelect: () => void
}) {
  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded shadow-xs flex flex-col overflow-hidden">

      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800">
        <span className="text-sm font-semibold font-mono">{name}</span>
        <button
          onClick={onSelect}
          className="text-xs text-blue-500 dark:text-blue-400 hover:text-blue-600 dark:hover:text-blue-300 transition-colors flex items-center gap-1"
        >
          View charts
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <div className="px-4 py-3">
        <MicrogridInfoPanel history={history} config={config} stepSize={stepSize} />
      </div>

    </div>
  )
}

export function OverviewTab({ experiment, onSelectMicrogrid }: Props) {
  const { metadata, timeseriesByMicrogrid, configByMicrogrid } = experiment
  const env = metadata.environment
  const exec = metadata.execution
  const stepSize = env?.step_size ?? 300
  const microgrids = Object.keys(timeseriesByMicrogrid).sort()

  return (
    <div className="px-6 py-6 flex flex-col gap-6">

      {env && (
        <div className="flex flex-col gap-1">
          <p className="text-sm font-mono">
            {fmtDate(env.sim_start)}
            <span className="text-gray-400 mx-2">→</span>
            {fmtDate(env.sim_end)}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs font-mono text-gray-500">
            <span>{fmtSimDuration(env.sim_start, env.sim_end)} simulated</span>
            <span>{env.step_size}s steps</span>
            {exec?.duration != null && <span>{fmtRuntime(exec.duration)} runtime</span>}
            {exec?.git_hash && <span>git {exec.git_hash.slice(0, 7)}</span>}
          </div>
        </div>
      )}

      <div className={`grid gap-4 ${microgrids.length === 1 ? 'max-w-sm' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'}`}>
        {microgrids.map((mg) => (
          <MicrogridCard
            key={mg}
            name={mg}
            history={timeseriesByMicrogrid[mg]}
            config={configByMicrogrid[mg]}
            stepSize={stepSize}
            onSelect={() => onSelectMicrogrid(mg)}
          />
        ))}
      </div>

    </div>
  )
}
