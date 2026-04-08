import { useMemo } from 'react'
import type { ReactNode } from 'react'
import type { MicrogridState, MicrogridConfig } from '../api/types'
import { formatW } from './charts/shared'

// ── Helpers ───────────────────────────────────────────────────────────────────

export function fmtEnergy(wh: number): string {
  if (wh >= 1_000_000) return `${(wh / 1_000_000).toFixed(2)} MWh`
  if (wh >= 1000) return `${(wh / 1000).toFixed(2)} kWh`
  return `${wh.toFixed(0)} Wh`
}

export function actorsByMode(history: MicrogridState[], mode: 'producers' | 'consumers'): string[] {
  const names = new Set<string>()
  for (const s of history) {
    for (const [name, a] of Object.entries(s.actor_states)) {
      if (mode === 'producers' ? a.power >= 0 : a.power < 0) names.add(name)
    }
  }
  return Array.from(names)
}

export function computeSummary(history: MicrogridState[], stepSize: number) {
  let produced = 0, consumed = 0, gridExported = 0, gridImported = 0, socDeltas = 0
  const dtH = stepSize / 3600
  for (const s of history) {
    for (const a of Object.values(s.actor_states)) {
      if (a.power >= 0) produced += a.power * dtH
      else consumed += Math.abs(a.power) * dtH
    }
    if (s.p_grid > 0) gridExported += s.p_grid * dtH
    else gridImported += Math.abs(s.p_grid) * dtH
  }
  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1], curr = history[i]
    if (prev.dispatch_states && curr.dispatch_states) {
      for (const name of Object.keys(curr.dispatch_states)) {
        const ps = prev.dispatch_states[name]?.soc
        const cs = curr.dispatch_states[name]?.soc
        if (ps != null && cs != null) socDeltas += Math.abs(cs - ps)
      }
    }
  }
  const selfSufficiency = consumed > 0 ? Math.max(0, 1 - gridImported / consumed) : 1
  return { produced, consumed, gridExported, gridImported, selfSufficiency, batteryCycles: socDeltas / 2 }
}

// ── Component ─────────────────────────────────────────────────────────────────

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="truncate">{label}</span>
      {children}
    </div>
  )
}

function Divider() {
  return <div className="border-t border-gray-100 dark:border-gray-800 my-1" />
}

export function MicrogridInfoPanel({ history, config, stepSize }: {
  history: MicrogridState[]
  config: MicrogridConfig
  stepSize: number
}) {
  const latest = history[history.length - 1]
  const producers = useMemo(() => actorsByMode(history, 'producers'), [history])
  const consumers = useMemo(() => actorsByMode(history, 'consumers'), [history])
  const summary = useMemo(() => computeSummary(history, stepSize), [history, stepSize])

  return (
    <div className="text-xs flex flex-col gap-1">
      {/* Actors — current power */}
      {producers.map(name => (
        <Row key={name} label={name}>
          <span className="font-mono text-emerald-600 dark:text-emerald-400 shrink-0">
            {formatW(latest.actor_states[name]?.power ?? 0)}
          </span>
        </Row>
      ))}
      {consumers.map(name => (
        <Row key={name} label={name}>
          <span className="font-mono text-red-500 dark:text-red-400 shrink-0">
            {formatW(Math.abs(latest.actor_states[name]?.power ?? 0))}
          </span>
        </Row>
      ))}

      {/* Storage — current SoC */}
      {config.dispatch.length > 0 && (
        <>
          <Divider />
          {config.dispatch.map(d => {
            const pct = (latest.dispatch_states?.[d.name]?.soc ?? null)
            const pctNum = pct != null ? pct * 100 : null
            const color = pctNum == null ? ''
              : pctNum > 50 ? 'text-emerald-600 dark:text-emerald-400'
              : pctNum > 20 ? 'text-amber-500'
              : 'text-red-500 dark:text-red-400'
            return (
              <Row key={d.name} label={d.name}>
                {pctNum != null && (
                  <span className={`font-mono shrink-0 ${color}`}>{pctNum.toFixed(0)}%</span>
                )}
              </Row>
            )
          })}
        </>
      )}

      {/* Energy totals */}
      <Divider />
      <Row label="Produced">
        <span className="font-mono text-emerald-600 dark:text-emerald-400">{fmtEnergy(summary.produced)}</span>
      </Row>
      <Row label="Consumed">
        <span className="font-mono text-red-500 dark:text-red-400">{fmtEnergy(summary.consumed)}</span>
      </Row>
      <Row label="Grid export">
        <span className="font-mono text-blue-500 dark:text-blue-400">{fmtEnergy(summary.gridExported)}</span>
      </Row>
      <Row label="Grid import">
        <span className="font-mono text-amber-500">{fmtEnergy(summary.gridImported)}</span>
      </Row>
      <Row label="Self-sufficiency">
        <span className="font-mono">{(summary.selfSufficiency * 100).toFixed(0)}%</span>
      </Row>
      {summary.batteryCycles > 0 && (
        <Row label="Battery cycles">
          <span className="font-mono">{summary.batteryCycles.toFixed(1)}</span>
        </Row>
      )}

      {/* Policy */}
      <Divider />
      <span className="text-gray-500 font-mono">{config.policy.type}</span>

    </div>
  )
}
