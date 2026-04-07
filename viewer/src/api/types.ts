export interface ActorState {
  name: string
  signal: string
  power: number
}

export interface PolicyState {
  mode: string
  charge_power: number
}

export interface DispatchableState {
  soc: number | null
  charge_level: number | null
  capacity: number | null
  min_soc: number | null
  c_rate: number | null
  [key: string]: number | null | undefined
}

export interface GridSignals {
  carbon_intensity?: number | null
  cost?: number | null
  [key: string]: number | null | undefined
}

export interface MicrogridState {
  time: string
  p_delta: number
  p_grid: number
  actor_states: Record<string, ActorState>
  policy_state: PolicyState
  dispatch_states: Record<string, DispatchableState> | null
  grid_signals: GridSignals
}

export interface ActorConfig {
  name: string
  signal_type: string
  signal: string
  step_size: number | null
}

export interface DispatchableConfig {
  name: string
  type: string
  soc?: number | null
  capacity?: number | null
  min_soc?: number | null
  c_rate?: number | null
}

export interface PolicyConfig {
  type: string
  mode?: string
  charge_power?: number
}

export interface MicrogridConfig {
  name: string
  actors: ActorConfig[]
  dispatch: DispatchableConfig[]
  policy: PolicyConfig
  coords: [number, number] | null
}

export interface EnvironmentConfig {
  name: string | null
  sim_start: string
  step_size: number
  sim_end: string
}

export interface ExecutionInfo {
  status: 'running' | 'completed'
  git_hash: string | null
  start: string | null
  end: string | null
  duration: number | null
}
