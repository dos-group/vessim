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
      <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-4 shadow-xs opacity-40">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-600">Dispatch</span>
        <span className="text-sm text-gray-300 dark:text-gray-700">No dispatchables configured</span>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-4 shadow-xs">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-600">Dispatch</span>

      {/* Per-dispatchable current power */}
      <div className="flex flex-col gap-2">
        {names.map((name) => {
          const power = currentPower(name, latest, prev)
          const { label, color } = powerStatus(power)
          return (
            <div key={name} className="flex items-baseline justify-between">
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{name}</span>
                <span className={`text-[10px] font-medium ${color}`}>{label}</span>
              </div>
              <span className={`text-base font-semibold tabular-nums ${color}`}>
                {power !== null ? formatW(Math.abs(power)) : '—'}
              </span>
            </div>
          )
        })}
      </div>

      <DispatchChart history={history} />
    </div>
  )
}
