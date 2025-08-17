import type {GenericState, StepUpdateMessage, StorageState, SystemState} from "../lib/types.ts";
import {FiBatteryCharging, FiClock, FiHash, FiPower, FiServer, FiSun} from "react-icons/fi";
import dayjs from "dayjs";

function getDeltaPrefix(d: number) {
    if (d > 0)
        return "+"
    else
        return ""
}

export function StatsOverview({state}: {state: StepUpdateMessage | undefined}) {
    const states = Object.keys(state?.state ?? {})
    const batteryStorage = states
        .filter(s => s.includes("storage"))
        .map(s => state?.state[s] as StorageState)
        .reduce((acc, s) => {
            acc.capacity += (s.capacity);
            acc.actual += (s.capacity * (s.soc ?? 0));

            return acc;
        }, {capacity: 0, actual: 0});

    const computingSystemUsage = states
        .filter(s => s.includes("ComputingSystem"))
        .map(s => state?.state[s] as SystemState)
        .reduce((acc, s) => {
            return acc + s.p
        }, 0);

    const solarProduction = states
        .filter(s => s.includes("solar"))
        .map(s => state?.state[s] as GenericState)
        .reduce((acc, s) => {
            return acc + s.p
        }, 0)

    return (
        <div className={"m-8 mt-16"}>
            <h1 className={"text-3xl font-bold"}>Overview</h1>

            <div className={"flex justify-between gap-5"}>
                <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                    <div className="flex items-center mb-4">
                        <FiClock size={25} className={"text-indigo-300"}/>
                        <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                            Time
                        </h5>
                    </div>
                    <p className="block text-slate-600 leading-normal font-light mb-4">
                        Time of the last update received by the server. The time is relative to the simulation and, by
                        extension may not reflect the actual current time.
                    </p>
                    <div className={"mt-auto"}>
                        <h2 className={"text-xl font-bold text-indigo-700 font-mono"}>{dayjs(state?.time).format("DD.MM.YYYY HH:mm:ss")}</h2>
                    </div>
                </div>

                <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                    <div className="flex items-center mb-4">
                        <FiHash size={25} className={"text-indigo-300"}/>
                        <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                            Actors
                        </h5>
                    </div>
                    <p className="block text-slate-600 leading-normal font-light mb-4">
                        The number of actors that are currently contained within the grid. Consumers are usually
                        computing systems while producers can represent generators such as solar panels or wind turbines.
                    </p>
                    <div className={"mt-auto"}>
                        <h2 className={"text-xl font-bold text-indigo-700 font-mono"}>{Object.keys(state?.state ?? {}).filter(s => !s.includes("policy")).length}</h2>
                    </div>
                </div>

                <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                    <div className="flex items-center mb-4">
                        <FiPower size={25} className={"text-indigo-300"}/>
                        <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                            Power Delta
                        </h5>
                    </div>
                    <p className="block text-slate-600 leading-normal font-light mb-4">
                        The grid simulation continually aggregates the current power production/consumption of actors to calculate the power delta.
                    </p>
                    <div className={"mt-auto"}>
                        <h2 className={"text-xl font-bold text-indigo-700 font-mono"}>{getDeltaPrefix(state?.p_delta ?? 0)}{state?.p_delta.toFixed(1) ?? "N/A"} Wh</h2>
                    </div>
                </div>

                <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                    <div className="flex items-center mb-4">
                        <FiBatteryCharging size={25} className={"text-indigo-300"}/>
                        <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                            Stored Energy
                        </h5>
                    </div>
                    <p className="block text-slate-600 leading-normal font-light mb-4">
                        All energy currently stored in batteries across the grid. The total grid capacity is
                        <span className={"font-bold"}> {batteryStorage.capacity.toFixed(1)} Wh</span>.
                    </p>
                    <div className={"mt-auto"}>
                        <h2 className={"text-xl font-bold text-indigo-700 font-mono"}>{batteryStorage.actual.toFixed(1)} Wh ({((batteryStorage.actual / batteryStorage.capacity) * 100).toFixed(0)}%)</h2>
                    </div>
                </div>

                <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                    <div className="flex items-center mb-4">
                        <FiSun size={25} className={"text-indigo-300"}/>
                        <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                            Solar Energy
                        </h5>
                    </div>
                    <p className="block text-slate-600 leading-normal font-light mb-4">
                        All energy currently produced by solar panels.
                    </p>
                    <div className={"mt-auto"}>
                        <h2 className={"text-xl font-bold text-indigo-700 font-mono"}>{solarProduction.toFixed(1)} Wh</h2>
                    </div>
                </div>

                <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                    <div className="flex items-center mb-4">
                        <FiServer size={25} className={"text-indigo-300"}/>
                        <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                            Computing Consumption
                        </h5>
                    </div>
                    <p className="block text-slate-600 leading-normal font-light mb-4">
                        All energy currently used by computing systems across the grid.
                    </p>
                    <div className={"mt-auto"}>
                        <h2 className={"text-xl font-bold text-red-800 font-mono"}>{computingSystemUsage.toFixed(1)} Wh</h2>
                    </div>
                </div>
            </div>
        </div>
    )
}