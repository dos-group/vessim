import type { MicrogridState } from '../api/types'
import { ActorsChart } from './charts/ActorsChart'
import { formatW } from './charts/shared'

interface Props {
  history: MicrogridState[]
  latest: MicrogridState
  mode: 'consumers' | 'producers'
}

// An actor belongs to a panel if it has ever had power in that direction across history.
// If it's been both, it appears in both.
function getActorNamesForMode(history: MicrogridState[], mode: 'consumers' | 'producers'): string[] {
  const names = new Set<string>()
  for (const s of history) {
    for (const [name, a] of Object.entries(s.actor_states)) {
      if (mode === 'consumers' && a.power < 0) names.add(name)
      if (mode === 'producers' && a.power > 0) names.add(name)
    }
  }
  return Array.from(names)
}

export function ActorPanel({ history, latest, mode }: Props) {
  const actorNames = getActorNamesForMode(history, mode)

  // Current totals
  const actors = Object.values(latest.actor_states)
  const total = mode === 'consumers'
    ? actors.filter((a) => a.power < 0).reduce((s, a) => s + Math.abs(a.power), 0)
    : actors.filter((a) => a.power >= 0).reduce((s, a) => s + a.power, 0)

  const isIdle = total === 0 && actorNames.length === 0
  const dimmed = isIdle

  const title = mode === 'consumers' ? 'Consumers' : 'Producers'
  const accentColor = mode === 'consumers'
    ? 'text-red-500 dark:text-red-400'
    : 'text-emerald-600 dark:text-emerald-400'

  return (
    <div className={`bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-4 shadow-xs ${dimmed ? 'opacity-50' : ''}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-600">{title}</span>
      </div>

      {/* Current value */}
      <div>
        <span className={`text-3xl font-semibold tabular-nums ${accentColor}`}>
          {formatW(total)}
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-600 ml-2">now</span>
      </div>

      {/* Chart */}
      <ActorsChart history={history} mode={mode} />

      {/* Actor list */}
      {actorNames.length > 0 && (
        <div className="flex flex-col gap-1.5 border-t border-gray-100 dark:border-gray-800 pt-3">
          {actorNames.map((name) => {
            const state = latest.actor_states[name]
            const power = state?.power ?? 0
            const signal = state?.signal ?? ''
            // Truncate long signal strings
            const signalShort = signal.length > 60 ? signal.slice(0, 57) + '…' : signal
            return (
              <div key={name} className="flex items-baseline justify-between gap-2">
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{name}</span>
                  <span className="text-[10px] text-gray-400 dark:text-gray-600 font-mono truncate" title={signal}>
                    {signalShort}
                  </span>
                </div>
                <span className={`text-xs font-mono tabular-nums shrink-0 ${mode === 'consumers' ? 'text-red-400 dark:text-red-400' : 'text-emerald-500 dark:text-emerald-400'}`}>
                  {formatW(Math.abs(power))}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
