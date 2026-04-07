import type { MicrogridState } from '../api/types'
import { GridChart } from './charts/GridChart'
import { formatW } from './charts/shared'

interface Props {
  history: MicrogridState[]
  latest: MicrogridState
}

export function GridPanel({ history, latest }: Props) {
  const { p_grid } = latest
  const importing = p_grid > 0
  const exporting = p_grid < 0
  const balanced = p_grid === 0

  const valueColor = importing
    ? 'text-red-500 dark:text-red-400'
    : exporting
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-gray-500 dark:text-gray-500'
  const dirLabel = importing ? 'importing' : exporting ? 'exporting' : 'balanced'

  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-3 shadow-xs">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 dark:text-gray-400">
          Grid Exchange
        </span>
        <div className="flex items-center gap-1.5">
          <span className={`text-sm font-semibold tabular-nums font-mono ${valueColor}`}>
            {balanced ? '0 W' : formatW(Math.abs(p_grid))}
          </span>
          <span className="text-[10px] text-gray-400 dark:text-gray-500">{dirLabel}</span>
        </div>
      </div>
      <GridChart history={history} />
    </div>
  )
}
