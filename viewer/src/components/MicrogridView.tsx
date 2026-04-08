import { useState } from 'react'
import type { ReactNode } from 'react'
import type { MicrogridState, MicrogridConfig } from '../api/types'
import type { ExperimentMetadata } from '../data/parser'
import { ActorsChart } from './charts/ActorsChart'
import { PowerBalanceChart } from './charts/PowerBalanceChart'
import { GridChart } from './charts/GridChart'
import { DispatchChart } from './charts/DispatchChart'
import { SocChart } from './charts/SocChart'
import { MicrogridInfoPanel } from './MicrogridInfoPanel'
import { actorsByMode } from './MicrogridInfoPanel'

interface Props {
  name: string
  allHistory: Record<string, MicrogridState[]>
  history: MicrogridState[]
  config: MicrogridConfig
  metadata: ExperimentMetadata
}

const CHART_H = 150

// ── UI primitives ─────────────────────────────────────────────────────────────

const chevron = (collapsed: boolean) => (
  <svg
    className={`w-3 h-3 text-gray-400 transition-transform duration-150 shrink-0 ${collapsed ? '-rotate-90' : ''}`}
    fill="none" stroke="currentColor" viewBox="0 0 24 24"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
)

export function CollapsibleCard({
  label, extra, children, defaultCollapsed = false,
}: {
  label: string
  extra?: ReactNode
  children?: ReactNode
  defaultCollapsed?: boolean
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)
  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded shadow-xs overflow-hidden">
      <div
        role="button"
        onClick={() => setCollapsed((v) => !v)}
        className={`flex items-center gap-2 px-4 py-2 cursor-pointer select-none hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors ${!collapsed ? 'border-b border-gray-100 dark:border-gray-800' : ''}`}
      >
        {chevron(collapsed)}
        <span className="text-xs font-medium">{label}</span>
        {extra != null && (
          <div className="ml-auto" onClick={(e) => e.stopPropagation()}>
            {extra}
          </div>
        )}
      </div>
      {!collapsed && children}
    </div>
  )
}

export function InnerCollapsible({ label, children }: { label: string; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <>
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2 border-t border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors"
      >
        {chevron(collapsed)}
        <span className="text-xs font-medium">{label}</span>
      </button>
      {!collapsed && children}
    </>
  )
}

function StackToggle({ stacked, onChange }: { stacked: boolean; onChange: (v: boolean) => void }) {
  const base = 'px-2 py-0.5 text-xs rounded transition-colors'
  const active = 'bg-white dark:bg-gray-700 shadow-xs'
  const inactive = 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
  return (
    <div className="flex items-center gap-0.5 bg-gray-100 dark:bg-gray-800 rounded p-0.5">
      <button className={`${base} ${!stacked ? active : inactive}`} onClick={() => onChange(false)}>Lines</button>
      <button className={`${base} ${stacked ? active : inactive}`} onClick={() => onChange(true)}>Stacked</button>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function MicrogridView({ name, history, config, metadata }: Props) {
  const [stackedProducers, setStackedProducers] = useState(false)
  const [stackedConsumers, setStackedConsumers] = useState(false)

  if (!history || history.length === 0) {
    return (
      <div className="flex items-center justify-center py-32 text-gray-500 text-sm">
        No data available for this microgrid.
      </div>
    )
  }

  const stepSize = metadata.environment?.step_size ?? 300
  const producerNames = actorsByMode(history, 'producers')
  const consumerNames = actorsByMode(history, 'consumers')
  const hasDispatch = config.dispatch.length > 0
  const latest = history[history.length - 1]
  const dispatchNames = latest.dispatch_states ? Object.keys(latest.dispatch_states) : []

  return (
    <div className="flex gap-6 items-start">

      {/* ── Left info column ──────────────────────────────────────────────── */}
      <div className="w-52 shrink-0 sticky top-6 max-h-[calc(100vh-3.5rem)] overflow-y-auto pb-6 flex flex-col gap-4">
        <h1 className="text-base font-bold font-mono">{name}</h1>
        <MicrogridInfoPanel history={history} config={config} stepSize={stepSize} />
      </div>

      {/* ── Right charts column ───────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col gap-2">

        {/* Power Balance + Actors */}
        <CollapsibleCard label="Power Balance">
          <PowerBalanceChart history={history} height={CHART_H} />
          <InnerCollapsible label="Actors">
            <div className="border-t border-gray-100 dark:border-gray-800">
              <div className="flex items-center justify-between px-4 py-1.5 border-b border-gray-100 dark:border-gray-800">
                <span className="text-xs">Consumers</span>
                {consumerNames.length > 1 && (
                  <StackToggle stacked={stackedConsumers} onChange={setStackedConsumers} />
                )}
              </div>
              <ActorsChart history={history} mode="consumers" stacked={stackedConsumers} height={CHART_H} />
            </div>
            {producerNames.length > 0 && (
              <div className="border-t border-gray-100 dark:border-gray-800">
                <div className="flex items-center justify-between px-4 py-1.5 border-b border-gray-100 dark:border-gray-800">
                  <span className="text-xs">Producers</span>
                  {producerNames.length > 1 && (
                    <StackToggle stacked={stackedProducers} onChange={setStackedProducers} />
                  )}
                </div>
                <ActorsChart history={history} mode="producers" stacked={stackedProducers} height={CHART_H} />
              </div>
            )}
          </InnerCollapsible>
        </CollapsibleCard>

        {/* Dispatch */}
        <CollapsibleCard label="Dispatch" defaultCollapsed={!hasDispatch}>
          {hasDispatch ? (
            <DispatchChart history={history} height={CHART_H} />
          ) : (
            <p className="px-4 py-3 text-xs text-gray-500">(No dispatchables)</p>
          )}
        </CollapsibleCard>

        {/* Grid Exchange */}
        <CollapsibleCard label="Grid Exchange">
          <GridChart history={history} height={CHART_H} />
        </CollapsibleCard>

        {/* Energy Storage */}
        {hasDispatch && (
          <CollapsibleCard
            label="Energy Storage"
            extra={
              <div className="flex items-center gap-2">
                {dispatchNames.map((name) => {
                  const soc = latest.dispatch_states?.[name]?.soc
                  if (soc == null) return null
                  const pct = soc * 100
                  const color = pct > 50 ? 'text-emerald-600 dark:text-emerald-400'
                    : pct > 20 ? 'text-amber-500'
                    : 'text-red-500 dark:text-red-400'
                  return (
                    <span key={name} className={`text-xs font-mono ${color}`}>
                      {dispatchNames.length > 1 ? `${name}: ` : ''}{pct.toFixed(0)}%
                    </span>
                  )
                })}
              </div>
            }
          >
            <SocChart history={history} height={CHART_H} />
          </CollapsibleCard>
        )}

      </div>
    </div>
  )
}
