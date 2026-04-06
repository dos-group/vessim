import yaml from 'js-yaml'
import Papa from 'papaparse'
import type {
  MicrogridState,
  MicrogridConfig,
  ActorState,
  DispatchableState,
  GridSignals,
  PolicyState,
} from '../api/types'

export interface MicrogridMetadata {
  actors: { name: string; signal_type: string; signal: string; step_size: number | null }[]
  dispatchables: { name: string; type: string; [key: string]: unknown }[]
  policy: { type: string; [key: string]: unknown }
  coords: [number, number] | null
}

export interface ExperimentMetadata {
  status: 'running' | 'completed' | undefined
  microgrids: Record<string, MicrogridMetadata>
}

export function parseConfig(yamlText: string): ExperimentMetadata {
  const raw = yaml.load(yamlText) as Record<string, unknown>
  return {
    status: (raw.status as ExperimentMetadata['status']) ?? undefined,
    microgrids: raw.microgrids as Record<string, MicrogridMetadata>,
  }
}

export function deriveConfigs(metadata: ExperimentMetadata): Record<string, MicrogridConfig> {
  const configs: Record<string, MicrogridConfig> = {}
  for (const [name, mg] of Object.entries(metadata.microgrids)) {
    configs[name] = {
      name,
      actors: mg.actors.map((a) => ({
        name: a.name,
        signal_type: a.signal_type,
        signal: a.signal,
        step_size: a.step_size,
      })),
      dispatch: mg.dispatchables.map((d) => ({
        name: d.name,
        type: d.type,
        soc: (d.soc as number) ?? null,
        capacity: (d.capacity as number) ?? null,
        min_soc: (d.min_soc as number) ?? null,
        c_rate: (d.c_rate as number) ?? null,
      })),
      policy: {
        type: mg.policy.type,
        mode: mg.policy.mode as string | undefined,
        charge_power: mg.policy.charge_power as number | undefined,
      },
      coords: mg.coords,
    }
  }
  return configs
}

function unflatten(row: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(row)) {
    const parts = key.split('.')
    let current = result as Record<string, unknown>
    for (let i = 0; i < parts.length - 1; i++) {
      if (!(parts[i] in current)) current[parts[i]] = {}
      current = current[parts[i]] as Record<string, unknown>
    }
    current[parts[parts.length - 1]] = value
  }
  return result
}

export function parseTimeseries(
  csvText: string,
  metadata: ExperimentMetadata,
): Record<string, MicrogridState[]> {
  const parsed = Papa.parse<Record<string, unknown>>(csvText, {
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
  })

  const result: Record<string, MicrogridState[]> = {}

  for (const row of parsed.data) {
    const mgName = row.microgrid as string
    if (!mgName) continue

    const meta = metadata.microgrids[mgName]
    if (!meta) continue

    // Remove microgrid column before unflattening
    const { microgrid: _, ...rest } = row
    const unflat = unflatten(rest)

    // Build actor_states — merge CSV power with metadata name/signal
    const actorStates: Record<string, ActorState> = {}
    const rawActors = (unflat.actor_states ?? {}) as Record<string, Record<string, unknown>>
    for (const [actorName, csvState] of Object.entries(rawActors)) {
      const actorMeta = meta.actors.find((a) => a.name === actorName)
      actorStates[actorName] = {
        name: actorName,
        signal: actorMeta?.signal ?? String(csvState.signal ?? ''),
        power: Number(csvState.power ?? 0),
      }
    }

    // Build dispatch_states — merge CSV dynamic state with metadata static config
    let dispatchStates: Record<string, DispatchableState> | null = null
    const rawDispatch = (unflat.dispatch_states ?? {}) as Record<
      string,
      Record<string, unknown>
    >
    if (Object.keys(rawDispatch).length > 0) {
      dispatchStates = {}
      for (const [dName, csvState] of Object.entries(rawDispatch)) {
        const dMeta = meta.dispatchables.find((d) => d.name === dName)
        dispatchStates[dName] = {
          soc: csvState.soc != null ? Number(csvState.soc) : null,
          charge_level: csvState.charge_level != null ? Number(csvState.charge_level) : null,
          capacity: (dMeta?.capacity as number) ?? null,
          min_soc: (dMeta?.min_soc as number) ?? null,
          c_rate: (dMeta?.c_rate as number) ?? null,
        }
      }
    }

    // Build policy_state
    const rawPolicy = (unflat.policy_state ?? {}) as Record<string, unknown>
    const policyState: PolicyState = {
      mode: String(rawPolicy.mode ?? ''),
      charge_power: Number(rawPolicy.charge_power ?? 0),
    }

    // Build grid_signals
    let gridSignals: GridSignals = {}
    const rawGrid = unflat.grid_signals
    if (rawGrid != null && typeof rawGrid === 'object') {
      gridSignals = rawGrid as GridSignals
    }

    const state: MicrogridState = {
      time: String(unflat.time),
      p_delta: Number(unflat.p_delta),
      p_grid: Number(unflat.p_grid),
      actor_states: actorStates,
      policy_state: policyState,
      dispatch_states: dispatchStates,
      grid_signals: gridSignals,
    }

    if (!result[mgName]) result[mgName] = []
    result[mgName].push(state)
  }

  return result
}
