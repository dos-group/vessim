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
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-4 shadow-xs">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-600">
        Power Balance
      </span>

      <div>
        <span className={`text-3xl font-semibold tabular-nums ${valueColor}`}>
          {formatW(delta)}
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-600 ml-2">{label}</span>
      </div>

      <PowerBalanceChart history={history} />
    </div>
  )
}
