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
    ? 'text-amber-500 dark:text-amber-400'
    : exporting
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-gray-500 dark:text-gray-500'
  const dirLabel = importing ? 'importing' : exporting ? 'exporting' : 'balanced'

  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 flex flex-col gap-4 shadow-xs">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-600">
        Grid Exchange
      </span>

      <div>
        <span className={`text-3xl font-semibold tabular-nums ${valueColor}`}>
          {balanced ? '0 W' : formatW(Math.abs(p_grid))}
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-600 ml-2">{dirLabel}</span>
      </div>

      <GridChart history={history} />
    </div>
  )
}
