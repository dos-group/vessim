import type {GenericState, StepUpdateMessage, StorageState, SystemState} from "../lib/types.ts";
import * as React from "react";
import {FiBatteryCharging, FiServer, FiWind} from "react-icons/fi";

function RenderIf({children, b}: {children: React.ReactNode, b: boolean}) {
    if (b) {
        return children;
    }

    return <></>;
}

export function DetailView({state}: {state: StepUpdateMessage | undefined}) {
    const [actor, setActor] = React.useState<string>("");

    function selectOnChange(e: React.ChangeEvent<HTMLSelectElement>) {
        e.preventDefault();
        setActor(e.currentTarget.value);
    }

    return (
        <div className={"m-8"}>
            <h1 className={"text-3xl font-bold"}>Actor Selection</h1>

            <select onChange={selectOnChange} id="countries" className="mt-3 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5">
                <option value={""} selected>Please Select...</option>
                <option value={"ComputingSystem"}>Computing System</option>
                <option value={"solar"}>Solar Production</option>
                <option value={"storage"}>Storage</option>
            </select>

            <div className={"flex gap-5"}>
                <RenderIf b={actor == "ComputingSystem"}>
                    {
                        Object.keys(state?.state ?? {})
                            .filter(k => k.includes("ComputingSystem"))
                            .map(s => ({key: s, value: state?.state[s] as SystemState}))
                            .map(s => {
                                return (
                                    <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                                        <div className="flex items-center mb-4">
                                            <FiServer size={25} className={"text-indigo-300"}/>
                                            <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                                                "{s.key}"
                                            </h5>
                                        </div>
                                        <div>
                                            <pre className={"bg-gray-100 p-3 rounded-md"}>
                                                {JSON.stringify(s.value.nodes, null, 2)}
                                            </pre>
                                        </div>
                                        <div className={"mt-3"}>
                                            <h2 className={"text-xl font-bold text-red-800 font-mono"}>{s.value.p.toFixed(1)} Wh</h2>
                                        </div>
                                    </div>
                                )
                            })
                    }
                </RenderIf>

                <RenderIf b={actor == "solar"}>
                    {
                        Object.keys(state?.state ?? {})
                            .filter(k => k.includes("solar"))
                            .map(s => ({key: s, value: state?.state[s] as GenericState}))
                            .map(s => {
                                return (
                                    <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                                        <div className="flex items-center mb-4">
                                            <FiWind size={25} className={"text-indigo-300"}/>
                                            <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                                                "{s.key}"
                                            </h5>
                                        </div>
                                        <div className={"mt-3"}>
                                            <h2 className={"text-xl font-bold text-indigo-700 font-mono"}>{s.value.p.toFixed(1)} Wh</h2>
                                        </div>
                                    </div>
                                )
                            })
                    }
                </RenderIf>

                <RenderIf b={actor == "storage"}>
                    {
                        Object.keys(state?.state ?? {})
                            .filter(k => k.includes("storage"))
                            .map(s => ({key: s, value: state?.state[s] as StorageState}))
                            .map(s => {
                                return (
                                    <div className="relative flex flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg w-96 p-6">
                                        <div className="flex items-center mb-4">
                                            <FiBatteryCharging size={25} className={"text-indigo-300"}/>
                                            <h5 className="ml-3 text-slate-800 text-xl font-semibold">
                                                "{s.key}"
                                            </h5>
                                        </div>
                                        <div>
                                            <pre className={"bg-gray-100 p-3 rounded-md overflow-x-hidden"}>
                                                {JSON.stringify(s.value, null, 2)}
                                            </pre>
                                        </div>
                                        <div className={"mt-3"}>
                                            <h2 className={"text-xl font-bold text-indigo-700 font-mono"}>
                                                {(s.value.charge_level).toFixed(1)} Wh / {s.value.capacity} Wh
                                                ({((s.value.charge_level / s.value.capacity) * 100).toFixed(0)}%)
                                            </h2>
                                        </div>
                                    </div>
                                )
                            })
                    }
                </RenderIf>
            </div>
        </div>
    )
}