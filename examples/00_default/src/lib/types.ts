export type GenericState = {
    p: number
}

export type SystemState = GenericState & {
    nodes: {
        [key: string]: number
    }
}

export type PolicyState = {
    mode: string,
    charge_power: number
}

export type StorageState = {
    soc?: number,
    charge_level: number,
    capacity: number,
    min_soc: number,
    c_rate?: number
}

export type StepUpdateStateElement = GenericState | SystemState | PolicyState | StorageState;

export type StepUpdateState = {
    [x: string]: StepUpdateStateElement,
}

export type StepUpdateMessage = {
    time: Date,
    p_delta: number,
    e_delta: number,
    state: StepUpdateState
}