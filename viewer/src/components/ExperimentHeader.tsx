import type { EnvironmentConfig, ExecutionInfo, MicrogridState } from '../api/types'
import { formatW } from './charts/shared'

interface Props {
  environment: EnvironmentConfig | null
  execution: ExecutionInfo | null
  allHistory: Record<string, MicrogridState[]>
  stepSize: number
}

interface Stat {
  label: string
  value: string
  color: string
}

function computeStats(allHistory: Record<string, MicrogridState[]>, stepSize: number): Stat[] {
  let totalProduced = 0
  let totalConsumed = 0
  let gridImported = 0
  let gridExported = 0
  let peakProduction = 0
  let peakConsumption = 0
  let socDeltas = 0

  for (const history of Object.values(allHistory)) {
    for (const s of history) {
      const dtH = stepSize / 3600
      // Actors
      for (const a of Object.values(s.actor_states)) {
        if (a.power >= 0) {
          totalProduced += a.power * dtH
          peakProduction = Math.max(peakProduction, a.power)
        } else {
          totalConsumed += Math.abs(a.power) * dtH
          peakConsumption = Math.max(peakConsumption, Math.abs(a.power))
        }
      }
      // Grid
      if (s.p_grid > 0) gridImported += s.p_grid * dtH
      else gridExported += Math.abs(s.p_grid) * dtH
    }
    // Battery cycles
    for (let i = 1; i < history.length; i++) {
      const prev = history[i - 1]
      const curr = history[i]
      if (prev.dispatch_states && curr.dispatch_states) {
        for (const name of Object.keys(curr.dispatch_states)) {
          const prevSoc = prev.dispatch_states[name]?.soc
          const currSoc = curr.dispatch_states[name]?.soc
          if (prevSoc != null && currSoc != null) {
            socDeltas += Math.abs(currSoc - prevSoc)
          }
        }
      }
    }
  }

  const selfSufficiency = totalConsumed > 0 ? Math.max(0, 1 - gridImported / (totalConsumed)) : 1
  const batteryCycles = socDeltas / 2

  function fmtEnergy(wh: number): string {
    if (wh >= 1000) return `${(wh / 1000).toFixed(1)} kWh`
    return `${wh.toFixed(0)} Wh`
  }

  return [
    { label: 'Produced', value: fmtEnergy(totalProduced), color: 'text-emerald-600 dark:text-emerald-400' },
    { label: 'Consumed', value: fmtEnergy(totalConsumed), color: 'text-red-500 dark:text-red-400' },
    { label: 'Grid import', value: fmtEnergy(gridImported), color: 'text-amber-500 dark:text-amber-400' },
    { label: 'Grid export', value: fmtEnergy(gridExported), color: 'text-blue-500 dark:text-blue-400' },
    { label: 'Peak prod.', value: formatW(peakProduction), color: 'text-emerald-600 dark:text-emerald-400' },
    { label: 'Peak cons.', value: formatW(peakConsumption), color: 'text-red-500 dark:text-red-400' },
    { label: 'Self-suff.', value: `${(selfSufficiency * 100).toFixed(0)}%`, color: 'text-gray-700 dark:text-gray-300' },
    { label: 'Batt. cycles', value: batteryCycles.toFixed(1), color: 'text-gray-700 dark:text-gray-300' },
  ]
}

function formatDate(iso: string): string {
  const d = new Date(iso.replace(' ', 'T'))
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatDuration(seconds: number): string {
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  return `${(seconds / 60).toFixed(1)}min`
}

function simDuration(start: string, end: string): string {
  const ms = new Date(end.replace(' ', 'T')).getTime() - new Date(start.replace(' ', 'T')).getTime()
  const hours = ms / 3_600_000
  if (hours >= 24) return `${(hours / 24).toFixed(1)}d`
  return `${hours.toFixed(0)}h`
}

export function ExperimentHeader({ environment, execution, allHistory, stepSize }: Props) {
  const stats = computeStats(allHistory, stepSize)

  return (
    <div className="flex flex-col gap-4 mb-6">
      {/* Experiment info */}
      {environment && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono">
          <span className="text-gray-700 dark:text-gray-300">
            {formatDate(environment.sim_start)} &rarr; {formatDate(environment.sim_end)}
          </span>
          <span className="text-gray-400 dark:text-gray-600">
            {simDuration(environment.sim_start, environment.sim_end)} simulated
          </span>
          <span className="text-gray-400 dark:text-gray-600">
            {environment.step_size}s steps
          </span>
          {execution?.duration != null && (
            <span className="text-gray-400 dark:text-gray-600">
              {formatDuration(execution.duration)} runtime
            </span>
          )}
          {execution?.git_hash && (
            <span className="text-gray-400 dark:text-gray-600">
              git {execution.git_hash.slice(0, 7)}
            </span>
          )}
        </div>
      )}

      {/* Summary stats */}
      <div className="grid grid-cols-4 md:grid-cols-8 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-500">
              {s.label}
            </span>
            <span className={`text-sm font-semibold font-mono tabular-nums ${s.color}`}>
              {s.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
