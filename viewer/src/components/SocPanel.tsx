import type { MicrogridState, MicrogridConfig } from '../api/types'
import { SocChart } from './charts/SocChart'

interface Props {
  history: MicrogridState[]
  latest: MicrogridState
  config?: MicrogridConfig
}

export function SocPanel({ history, latest, config }: Props) {
  const dispatchStates = latest.dispatch_states
  const names = dispatchStates ? Object.keys(dispatchStates) : []
  const hasDispatch = names.length > 0

  if (!hasDispatch) {
    return (
      <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-3 shadow-xs opacity-40">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 dark:text-gray-400">
          State of Charge
        </span>
        <span className="text-sm text-gray-400 dark:text-gray-600">No dispatchables configured</span>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-3 shadow-xs">
      {/* Header with SoC values inline */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 dark:text-gray-400">
          State of Charge
        </span>
        <div className="flex items-center gap-3">
          {names.map((name) => {
            const soc = (dispatchStates![name].soc ?? 0) * 100
            const socColor = soc > 50
              ? 'text-emerald-600 dark:text-emerald-400'
              : soc > 20
              ? 'text-amber-500 dark:text-amber-400'
              : 'text-red-500 dark:text-red-400'
            return (
              <div key={name} className="flex items-center gap-1">
                {names.length > 1 && (
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">{name}</span>
                )}
                <span className={`text-sm font-semibold tabular-nums font-mono ${socColor}`}>
                  {soc.toFixed(1)}%
                </span>
              </div>
            )
          })}
        </div>
      </div>

      <SocChart history={history} />

      {/* Config details */}
      {config?.dispatch && config.dispatch.length > 0 && (
        <div className="flex flex-col gap-1.5 border-t border-gray-100 dark:border-gray-800 pt-3">
          {config.dispatch.map((d) => (
            <div key={d.name} className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
              <span className="text-[10px] font-medium text-gray-600 dark:text-gray-400">{d.name}</span>
              <span className="text-[10px] font-mono text-gray-400 dark:text-gray-600">{d.type}</span>
              {d.min_soc != null && (
                <span className="text-[10px] font-mono text-gray-400 dark:text-gray-600">
                  min_soc: {(d.min_soc * 100).toFixed(0)}%
                </span>
              )}
              {d.c_rate != null
                ? <span className="text-[10px] font-mono text-gray-400 dark:text-gray-600">C-rate: {d.c_rate}</span>
                : <span className="text-[10px] font-mono text-gray-300 dark:text-gray-700">C-rate: —</span>
              }
              {d.capacity != null && (
                <span className="text-[10px] font-mono text-gray-400 dark:text-gray-600">{d.capacity} Wh</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
