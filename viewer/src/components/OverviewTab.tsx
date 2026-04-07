import type { MicrogridState, MicrogridConfig } from '../api/types'
import type { LoadedExperiment } from '../data/fileLoader'
import { formatW } from './charts/shared'

interface Props {
  experiment: LoadedExperiment
  onSelectMicrogrid: (name: string) => void
}

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  const d = new Date(iso.replace(' ', 'T'))
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
    + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtSimDuration(start: string, end: string): string {
  const hours = (new Date(end.replace(' ', 'T')).getTime() - new Date(start.replace(' ', 'T')).getTime()) / 3_600_000
  return hours >= 24 ? `${(hours / 24).toFixed(1)}d` : `${hours.toFixed(0)}h`
}

function fmtRuntime(sec: number): string {
  if (sec < 1) return `${(sec * 1000).toFixed(0)}ms`
  if (sec < 60) return `${sec.toFixed(1)}s`
  return `${(sec / 60).toFixed(1)}min`
}

function fmtEnergy(wh: number): string {
  if (wh >= 1_000_000) return `${(wh / 1_000_000).toFixed(2)} MWh`
  if (wh >= 1000) return `${(wh / 1000).toFixed(2)} kWh`
  return `${wh.toFixed(0)} Wh`
}

// ── Per-microgrid summary ─────────────────────────────────────────────────────

function computeMgSummary(history: MicrogridState[], stepSize: number) {
  let produced = 0, consumed = 0, gridExported = 0, gridImported = 0
  const dtH = stepSize / 3600
  for (const s of history) {
    for (const a of Object.values(s.actor_states)) {
      if (a.power >= 0) produced += a.power * dtH
      else consumed += Math.abs(a.power) * dtH
    }
    if (s.p_grid > 0) gridExported += s.p_grid * dtH
    else gridImported += Math.abs(s.p_grid) * dtH
  }
  const selfSufficiency = consumed > 0 ? Math.max(0, 1 - gridImported / consumed) : 1
  return { produced, consumed, gridExported, gridImported, selfSufficiency }
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

// ── Sub-components ────────────────────────────────────────────────────────────

function Kv({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[10px] text-gray-500 dark:text-gray-400 shrink-0">{label}</span>
      <span className={`text-xs font-mono tabular-nums text-right ${color ?? 'text-gray-700 dark:text-gray-300'}`}>
        {value}
      </span>
    </div>
  )
}

function SectionLabel({ children }: { children: string }) {
  return (
    <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
      {children}
    </span>
  )
}

function MicrogridCard({
  name, history, config, stepSize, onSelect,
}: {
  name: string
  history: MicrogridState[]
  config: MicrogridConfig
  stepSize: number
  onSelect: () => void
}) {
  const latest = history[history.length - 1]
  const producers = actorsByMode(history, 'producers')
  const consumers = actorsByMode(history, 'consumers')
  const summary = computeMgSummary(history, stepSize)
  const hasDispatch = config.dispatch.length > 0

  return (
    <div className="bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded shadow-xs flex flex-col overflow-hidden">

      {/* Card header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 dark:border-gray-800">
        <span className="text-sm font-semibold text-gray-800 dark:text-gray-100 font-mono">{name}</span>
        <button
          onClick={onSelect}
          className="text-xs text-blue-500 dark:text-blue-400 hover:text-blue-600 dark:hover:text-blue-300 transition-colors flex items-center gap-1"
        >
          View charts
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <div className="flex flex-col gap-4 px-5 py-4">

        {/* Actors */}
        {(producers.length > 0 || consumers.length > 0) && (
          <div className="flex flex-col gap-1.5">
            <SectionLabel>Actors</SectionLabel>
            {producers.map((name) => {
              const a = latest.actor_states[name]
              const cfg = config.actors.find((c) => c.name === name)
              return (
                <div key={name} className="flex items-baseline justify-between gap-2">
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs text-gray-700 dark:text-gray-300 truncate">{name}</span>
                    {cfg?.signal_type && (
                      <span className="text-[10px] font-mono text-gray-400 dark:text-gray-600">{cfg.signal_type}</span>
                    )}
                  </div>
                  <span className="text-xs font-mono text-emerald-600 dark:text-emerald-400 shrink-0">
                    {formatW(a?.power ?? 0)}
                  </span>
                </div>
              )
            })}
            {producers.length > 0 && consumers.length > 0 && (
              <div className="border-t border-gray-100 dark:border-gray-800 my-0.5" />
            )}
            {consumers.map((name) => {
              const a = latest.actor_states[name]
              const cfg = config.actors.find((c) => c.name === name)
              return (
                <div key={name} className="flex items-baseline justify-between gap-2">
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs text-gray-700 dark:text-gray-300 truncate">{name}</span>
                    {cfg?.signal_type && (
                      <span className="text-[10px] font-mono text-gray-400 dark:text-gray-600">{cfg.signal_type}</span>
                    )}
                  </div>
                  <span className="text-xs font-mono text-red-500 dark:text-red-400 shrink-0">
                    {formatW(Math.abs(a?.power ?? 0))}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {/* Dispatchables */}
        {hasDispatch && (
          <div className="flex flex-col gap-1.5">
            <SectionLabel>Storage</SectionLabel>
            {config.dispatch.map((d) => {
              const state = latest.dispatch_states?.[d.name]
              const soc = state?.soc != null ? state.soc * 100 : null
              const socColor = soc == null ? 'text-gray-400'
                : soc > 50 ? 'text-emerald-600 dark:text-emerald-400'
                : soc > 20 ? 'text-amber-500 dark:text-amber-400'
                : 'text-red-500 dark:text-red-400'
              return (
                <div key={d.name} className="flex flex-col gap-0.5">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs text-gray-700 dark:text-gray-300 truncate">{d.name}</span>
                    {soc != null && (
                      <span className={`text-xs font-mono shrink-0 ${socColor}`}>{soc.toFixed(1)}%</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-x-2 text-[10px] font-mono text-gray-400 dark:text-gray-600">
                    <span>{d.type}</span>
                    {d.capacity != null && <span>{fmtEnergy(d.capacity)}</span>}
                    {d.min_soc != null && <span>min {(d.min_soc * 100).toFixed(0)}%</span>}
                    {d.c_rate != null && <span>C {d.c_rate}</span>}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Policy */}
        <div className="flex flex-col gap-1">
          <SectionLabel>Policy</SectionLabel>
          <span className="text-xs font-mono text-gray-500 dark:text-gray-400">{config.policy.type}</span>
        </div>

        {/* Energy summary */}
        <div className="flex flex-col gap-1">
          <SectionLabel>Energy</SectionLabel>
          <Kv label="Produced" value={fmtEnergy(summary.produced)} color="text-emerald-600 dark:text-emerald-400" />
          <Kv label="Consumed" value={fmtEnergy(summary.consumed)} color="text-red-500 dark:text-red-400" />
          <Kv label="Grid export" value={fmtEnergy(summary.gridExported)} color="text-blue-500 dark:text-blue-400" />
          <Kv label="Grid import" value={fmtEnergy(summary.gridImported)} color="text-amber-500 dark:text-amber-400" />
          <Kv label="Self-sufficiency" value={`${(summary.selfSufficiency * 100).toFixed(0)}%`} />
        </div>

      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function OverviewTab({ experiment, onSelectMicrogrid }: Props) {
  const { metadata, timeseriesByMicrogrid, configByMicrogrid } = experiment
  const env = metadata.environment
  const exec = metadata.execution
  const stepSize = env?.step_size ?? 300
  const microgrids = Object.keys(timeseriesByMicrogrid).sort()

  return (
    <div className="px-6 py-6 flex flex-col gap-6">

      {/* Experiment metadata */}
      {env && (
        <div className="flex flex-col gap-1">
          <p className="text-sm font-mono text-gray-700 dark:text-gray-300">
            {fmtDate(env.sim_start)}
            <span className="text-gray-400 dark:text-gray-600 mx-2">→</span>
            {fmtDate(env.sim_end)}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs font-mono text-gray-400 dark:text-gray-600">
            <span>{fmtSimDuration(env.sim_start, env.sim_end)} simulated</span>
            <span>{env.step_size}s steps</span>
            {exec?.duration != null && <span>{fmtRuntime(exec.duration)} runtime</span>}
            {exec?.git_hash && <span>git {exec.git_hash.slice(0, 7)}</span>}
          </div>
        </div>
      )}

      {/* Microgrid cards */}
      <div className={`grid gap-4 ${microgrids.length === 1 ? 'max-w-sm' : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'}`}>
        {microgrids.map((mg) => (
          <MicrogridCard
            key={mg}
            name={mg}
            history={timeseriesByMicrogrid[mg]}
            config={configByMicrogrid[mg]}
            stepSize={stepSize}
            onSelect={() => onSelectMicrogrid(mg)}
          />
        ))}
      </div>

    </div>
  )
}
