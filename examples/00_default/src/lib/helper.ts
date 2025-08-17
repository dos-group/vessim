import type {GenericState, StepUpdateMessage, StorageState, SystemState} from "./types.ts";

export function calculateMetricsFromState(state: StepUpdateMessage | undefined) {
    const keys = Object.keys(state?.state ?? {});

    const batteryStorage = keys
        .filter(s => s.includes("storage"))
        .map(s => state?.state[s] as StorageState)
        .reduce((acc, s) => {
            acc.capacity += (s.capacity);
            acc.actual += (s.capacity * (s.soc ?? 0));

            return acc;
        }, {capacity: 0, actual: 0});

    const computingSystemUsage = keys
        .filter(s => s.includes("ComputingSystem"))
        .map(s => state?.state[s] as SystemState)
        .reduce((acc, s) => {
            return acc + s.p
        }, 0);

    const solarProduction = keys
        .filter(s => s.includes("solar"))
        .map(s => state?.state[s] as GenericState)
        .reduce((acc, s) => {
            return acc + s.p
        }, 0);

    return {
        battery: batteryStorage,
        computing: computingSystemUsage,
        solar: solarProduction,
    }
}