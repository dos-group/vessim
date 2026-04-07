import type { MicrogridState } from '../api/types'
import { PowerBalanceChart } from './charts/PowerBalanceChart'
import { formatW } from './charts/shared'

interface Props {
  history: MicrogridState[]
  latest: MicrogridState
}

export function BalancePanel({ history, latest }: Props) {
  const delta = latest.p_delta
  const positive = delta >= 0
  const valueColor = positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400'
  const label = positive ? 'surplus' : 'deficit'

  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-3 shadow-xs">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 dark:text-gray-400">
          Power Balance
        </span>
        <div className="flex items-center gap-1.5">
          <span className={`text-sm font-semibold tabular-nums font-mono ${valueColor}`}>
            {formatW(delta)}
          </span>
          <span className="text-[10px] text-gray-400 dark:text-gray-500">{label}</span>
        </div>
      </div>
      <PowerBalanceChart history={history} />
    </div>
  )
}
