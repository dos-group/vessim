import type { MicrogridState, MicrogridConfig } from '../api/types'
import type { ExperimentMetadata } from '../data/parser'
import { ExperimentHeader } from './ExperimentHeader'
import { ActorPanel } from './ActorPanel'
import { BalancePanel } from './BalancePanel'
import { DispatchPanel } from './DispatchPanel'
import { SocPanel } from './SocPanel'
import { GridPanel } from './GridPanel'

interface Props {
  allHistory: Record<string, MicrogridState[]>
  history: MicrogridState[]
  config: MicrogridConfig
  metadata: ExperimentMetadata
}

export function MicrogridView({ allHistory, history, config, metadata }: Props) {
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
      {/* Experiment header + summary stats */}
      <ExperimentHeader
        environment={metadata.environment}
        execution={metadata.execution}
        allHistory={allHistory}
        stepSize={metadata.environment?.step_size ?? 300}
      />

      {/* Row 1: Producers | Consumers | Balance */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ActorPanel history={history} latest={latest} mode="producers" />
        <ActorPanel history={history} latest={latest} mode="consumers" />
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
