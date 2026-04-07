import type { MicrogridState } from '../api/types'
import { DispatchChart } from './charts/DispatchChart'
import { formatW } from './charts/shared'

interface Props {
  history: MicrogridState[]
  latest: MicrogridState
  prev?: MicrogridState
}

function currentPower(name: string, latest: MicrogridState, prev?: MicrogridState): number | null {
  if (!prev) return null
  const curr = latest.dispatch_states?.[name]?.charge_level ?? null
  const prevLevel = prev.dispatch_states?.[name]?.charge_level ?? null
  if (curr === null || prevLevel === null) return null
  const dtHours = (new Date(latest.time).getTime() - new Date(prev.time).getTime()) / 3_600_000
  if (dtHours === 0) return null
  return (curr - prevLevel) / dtHours
}

function powerStatus(power: number | null): { label: string; color: string } {
  if (power === null) return { label: 'Unknown', color: 'text-gray-400 dark:text-gray-600' }
  if (power > 0.5) return { label: 'Charging', color: 'text-emerald-500 dark:text-emerald-400' }
  if (power < -0.5) return { label: 'Discharging', color: 'text-amber-500 dark:text-amber-400' }
  return { label: 'Idle', color: 'text-gray-400 dark:text-gray-600' }
}

export function DispatchPanel({ history, latest, prev }: Props) {
  const dispatchStates = latest.dispatch_states
  const names = dispatchStates ? Object.keys(dispatchStates) : []
  const hasDispatch = names.length > 0

  if (!hasDispatch) {
    return (
      <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-3 shadow-xs opacity-40">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 dark:text-gray-400">Dispatch</span>
        <span className="text-sm text-gray-400 dark:text-gray-600">No dispatchables configured</span>
      </div>
    )
  }

  // Show first dispatchable's power in header
  const firstPower = currentPower(names[0], latest, prev)
  const { label: firstLabel, color: firstColor } = powerStatus(firstPower)

  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-3 shadow-xs">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 dark:text-gray-400">Dispatch</span>
        <div className="flex items-center gap-1.5">
          <span className={`text-sm font-semibold tabular-nums font-mono ${firstColor}`}>
            {firstPower !== null ? formatW(Math.abs(firstPower)) : '\u2014'}
          </span>
          <span className={`text-[10px] ${firstColor}`}>{firstLabel}</span>
        </div>
      </div>

      <DispatchChart history={history} />

      {/* Per-dispatchable details (only if multiple) */}
      {names.length > 1 && (
        <div className="flex flex-col gap-1.5 border-t border-gray-100 dark:border-gray-800 pt-3">
          {names.map((name) => {
            const power = currentPower(name, latest, prev)
            const { label, color } = powerStatus(power)
            return (
              <div key={name} className="flex items-baseline justify-between">
                <div className="flex items-baseline gap-2">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{name}</span>
                  <span className={`text-[10px] font-medium ${color}`}>{label}</span>
                </div>
                <span className={`text-xs font-mono tabular-nums ${color}`}>
                  {power !== null ? formatW(Math.abs(power)) : '\u2014'}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
