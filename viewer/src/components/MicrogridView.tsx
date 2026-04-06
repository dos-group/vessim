import type { MicrogridState, MicrogridConfig } from '../api/types'
import { ActorPanel } from './ActorPanel'
import { BalancePanel } from './BalancePanel'
import { DispatchPanel } from './DispatchPanel'
import { SocPanel } from './SocPanel'
import { GridPanel } from './GridPanel'

interface Props {
  history: MicrogridState[]
  config: MicrogridConfig
}

export function MicrogridView({ history, config }: Props) {
  if (!history || history.length === 0) {
    return (
      <div className="flex items-center justify-center py-32 text-gray-300 text-sm">
        No data available for this microgrid.
      </div>
    )
  }

  const latest = history[history.length - 1]
  const prev = history.length > 1 ? history[history.length - 2] : undefined

  return (
    <div className="flex flex-col gap-4">
      {/* Row 1: Consumers | Producers | Balance */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ActorPanel history={history} latest={latest} mode="consumers" />
        <ActorPanel history={history} latest={latest} mode="producers" />
        <BalancePanel history={history} latest={latest} />
      </div>

      {/* Row 2: Dispatch | SoC | Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <DispatchPanel history={history} latest={latest} prev={prev} />
        <SocPanel history={history} latest={latest} config={config} />
        <GridPanel history={history} latest={latest} />
      </div>
    </div>
  )
}
