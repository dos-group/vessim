import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { MicrogridState, MicrogridConfig } from '../api/types'
import type { ExperimentMetadata } from '../data/parser'
import { ActorsChart } from './charts/ActorsChart'
import { PowerBalanceChart } from './charts/PowerBalanceChart'
import { GridChart } from './charts/GridChart'
import { DispatchChart } from './charts/DispatchChart'
import { SocChart } from './charts/SocChart'
import { formatW } from './charts/shared'

interface Props {
  allHistory: Record<string, MicrogridState[]>
  history: MicrogridState[]
  config: MicrogridConfig
  metadata: ExperimentMetadata
}

const CHART_H = 150

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtEnergy(wh: number): string {
  if (wh >= 1_000_000) return `${(wh / 1_000_000).toFixed(2)} MWh`
  if (wh >= 1000) return `${(wh / 1000).toFixed(2)} kWh`
  return `${wh.toFixed(0)} Wh`
}

function computeSummary(allHistory: Record<string, MicrogridState[]>, stepSize: number) {
  let produced = 0, consumed = 0, gridExported = 0, gridImported = 0, socDeltas = 0

  for (const history of Object.values(allHistory)) {
    const dtH = stepSize / 3600
    for (const s of history) {
      for (const a of Object.values(s.actor_states)) {
        if (a.power >= 0) produced += a.power * dtH
        else consumed += Math.abs(a.power) * dtH
      }
      // p_grid > 0 = exporting, p_grid < 0 = importing
      if (s.p_grid > 0) gridExported += s.p_grid * dtH
      else gridImported += Math.abs(s.p_grid) * dtH
    }
    for (let i = 1; i < history.length; i++) {
      const prev = history[i - 1]
      const curr = history[i]
      if (prev.dispatch_states && curr.dispatch_states) {
        for (const name of Object.keys(curr.dispatch_states)) {
          const ps = prev.dispatch_states[name]?.soc
          const cs = curr.dispatch_states[name]?.soc
          if (ps != null && cs != null) socDeltas += Math.abs(cs - ps)
        }
      }
    }
  }

  const selfSufficiency = consumed > 0 ? Math.max(0, 1 - gridImported / consumed) : 1
  return { produced, consumed, gridExported, gridImported, selfSufficiency, batteryCycles: socDeltas / 2 }
}

function actorsByMode(history: MicrogridState[], mode: 'producers' | 'consumers'): string[] {
  const names = new Set<string>()
  for (const s of history) {
    for (const [name, a] of Object.entries(s.actor_states)) {
      if (mode === 'producers' ? a.power >= 0 : a.power < 0) names.add(name)
    }
  }
  return Array.from(names)
}

// ── UI primitives ─────────────────────────────────────────────────────────────

const chevron = (collapsed: boolean) => (
  <svg
    className={`w-3 h-3 text-gray-300 dark:text-gray-700 transition-transform duration-150 shrink-0 ${collapsed ? '-rotate-90' : ''}`}
    fill="none" stroke="currentColor" viewBox="0 0 24 24"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
)

/**
 * Card with a collapsible body. Clicking the header row toggles visibility.
 * `extra` is rendered right-aligned in the header; clicks on it don't propagate.
 */
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
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {label}
        </span>
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

/**
 * In-card collapsible section — a clickable divider row that shows/hides its children.
 * Used to nest a secondary collapsible group inside a CollapsibleCard.
 */
export function InnerCollapsible({ label, children }: { label: string; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <>
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2 border-t border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors"
      >
        {chevron(collapsed)}
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {label}
        </span>
      </button>
      {!collapsed && children}
    </>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
        {title}
      </span>
      <div className="flex flex-col gap-1">{children}</div>
    </div>
  )
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[10px] text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
      <span className={`text-xs font-mono tabular-nums truncate text-right ${color ?? 'text-gray-700 dark:text-gray-300'}`}>
        {value}
      </span>
    </div>
  )
}

function StackToggle({ stacked, onChange }: { stacked: boolean; onChange: (v: boolean) => void }) {
  const base = 'px-2 py-0.5 text-[10px] rounded transition-colors'
  const active = 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 shadow-xs'
  const inactive = 'text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400'
  return (
    <div className="flex items-center gap-0.5 bg-gray-100 dark:bg-gray-800 rounded p-0.5">
      <button className={`${base} ${!stacked ? active : inactive}`} onClick={() => onChange(false)}>Lines</button>
      <button className={`${base} ${stacked ? active : inactive}`} onClick={() => onChange(true)}>Stacked</button>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function MicrogridView({ allHistory, history, config, metadata }: Props) {
  const [stackedProducers, setStackedProducers] = useState(false)
  const [stackedConsumers, setStackedConsumers] = useState(false)

  if (!history || history.length === 0) {
    return (
      <div className="flex items-center justify-center py-32 text-gray-300 text-sm">
        No data available for this microgrid.
      </div>
    )
  }

  const latest = history[history.length - 1]
  const stepSize = metadata.environment?.step_size ?? 300

  const producerNames = useMemo(() => actorsByMode(history, 'producers'), [history])
  const consumerNames = useMemo(() => actorsByMode(history, 'consumers'), [history])
  const summary = useMemo(() => computeSummary(allHistory, stepSize), [allHistory, stepSize])

  const dispatchNames = latest.dispatch_states ? Object.keys(latest.dispatch_states) : []
  const hasDispatch = dispatchNames.length > 0

  const gridExporting = latest.p_grid > 0
  const gridImporting = latest.p_grid < 0

  return (
    <div className="flex gap-6 items-start">

      {/* ── Left info column ──────────────────────────────────────────────── */}
      <div className="w-60 shrink-0 sticky top-6 max-h-[calc(100vh-3.5rem)] overflow-y-auto flex flex-col gap-5 pb-6">

        <Section title="Summary">
          <Row label="Produced" value={fmtEnergy(summary.produced)} color="text-emerald-600 dark:text-emerald-400" />
          <Row label="Consumed" value={fmtEnergy(summary.consumed)} color="text-red-500 dark:text-red-400" />
          <Row label="Grid export" value={fmtEnergy(summary.gridExported)} color="text-blue-500 dark:text-blue-400" />
          <Row label="Grid import" value={fmtEnergy(summary.gridImported)} color="text-amber-500 dark:text-amber-400" />
          <Row label="Self-sufficiency" value={`${(summary.selfSufficiency * 100).toFixed(0)}%`} />
          {summary.batteryCycles > 0 && (
            <Row label="Battery cycles" value={summary.batteryCycles.toFixed(1)} />
          )}
        </Section>

        {(producerNames.length > 0 || consumerNames.length > 0) && (
          <Section title="Actors">
            {producerNames.map((name) => {
              const state = latest.actor_states[name]
              return (
                <div key={name} className="flex flex-col gap-0.5 py-0.5">
                  <div className="flex items-baseline justify-between gap-1">
                    <span className="text-xs text-gray-700 dark:text-gray-300 truncate">{name}</span>
                    <span className="text-xs font-mono text-emerald-600 dark:text-emerald-400 shrink-0">
                      {formatW(state?.power ?? 0)}
                    </span>
                  </div>
                  {state?.signal && (
                    <span className="text-[10px] font-mono text-gray-400 dark:text-gray-600 truncate" title={state.signal}>
                      {state.signal}
                    </span>
                  )}
                </div>
              )
            })}
            {consumerNames.map((name) => {
              const state = latest.actor_states[name]
              return (
                <div key={name} className="flex flex-col gap-0.5 py-0.5">
                  <div className="flex items-baseline justify-between gap-1">
                    <span className="text-xs text-gray-700 dark:text-gray-300 truncate">{name}</span>
                    <span className="text-xs font-mono text-red-500 dark:text-red-400 shrink-0">
                      {formatW(Math.abs(state?.power ?? 0))}
                    </span>
                  </div>
                  {state?.signal && (
                    <span className="text-[10px] font-mono text-gray-400 dark:text-gray-600 truncate" title={state.signal}>
                      {state.signal}
                    </span>
                  )}
                </div>
              )
            })}
          </Section>
        )}

        {hasDispatch && config.dispatch.length > 0 && (
          <Section title="Dispatchers">
            {config.dispatch.map((d) => {
              const state = latest.dispatch_states?.[d.name]
              const soc = state?.soc != null ? state.soc * 100 : null
              const socColor =
                soc == null ? 'text-gray-400 dark:text-gray-600'
                : soc > 50 ? 'text-emerald-600 dark:text-emerald-400'
                : soc > 20 ? 'text-amber-500 dark:text-amber-400'
                : 'text-red-500 dark:text-red-400'
              return (
                <div key={d.name} className="flex flex-col gap-0.5 py-0.5">
                  <div className="flex items-baseline justify-between gap-1">
                    <span className="text-xs text-gray-700 dark:text-gray-300 truncate">{d.name}</span>
                    {soc != null && (
                      <span className={`text-xs font-mono shrink-0 ${socColor}`}>{soc.toFixed(1)}%</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] font-mono text-gray-400 dark:text-gray-600">
                    <span>{d.type}</span>
                    {d.capacity != null && <span>{fmtEnergy(d.capacity)}</span>}
                    {d.min_soc != null && <span>min {(d.min_soc * 100).toFixed(0)}%</span>}
                    {d.c_rate != null && <span>C {d.c_rate}</span>}
                  </div>
                </div>
              )
            })}
          </Section>
        )}

        <Section title="Dispatch Policy">
          <span className="text-[10px] font-mono text-gray-500 dark:text-gray-400">{config.policy.type}</span>
          {latest.policy_state.mode && (
            <Row label="mode" value={latest.policy_state.mode} />
          )}
        </Section>

      </div>

      {/* ── Right charts column ───────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col gap-2">

        {/* Power Balance + Actors */}
        <CollapsibleCard label="Power Balance">
          <PowerBalanceChart history={history} height={CHART_H} />
          <InnerCollapsible label="Actors">
            <div className="border-t border-gray-100 dark:border-gray-800">
              <div className="flex items-center justify-between px-4 py-1.5 border-b border-gray-100 dark:border-gray-800">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
                  Consumers
                </span>
                {consumerNames.length > 1 && (
                  <StackToggle stacked={stackedConsumers} onChange={setStackedConsumers} />
                )}
              </div>
              <ActorsChart history={history} mode="consumers" stacked={stackedConsumers} height={CHART_H} />
            </div>
            {producerNames.length > 0 && (
              <div className="border-t border-gray-100 dark:border-gray-800">
                <div className="flex items-center justify-between px-4 py-1.5 border-b border-gray-100 dark:border-gray-800">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
                    Producers
                  </span>
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
            <p className="px-4 py-3 text-[10px] text-gray-400 dark:text-gray-600">(No dispatchables)</p>
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
                    : pct > 20 ? 'text-amber-500 dark:text-amber-400'
                    : 'text-red-500 dark:text-red-400'
                  return (
                    <span key={name} className={`text-[10px] font-mono ${color}`}>
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
