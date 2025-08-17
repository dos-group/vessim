import type {StepUpdateMessage} from "../lib/types.ts";
import ReactApexChart from "react-apexcharts";
import ApexCharts, {type ApexOptions} from "apexcharts";
import {useEffect, useMemo, useRef, useState} from "react";
import dayjs, {Dayjs} from "dayjs";
import {calculateMetricsFromState} from "../lib/helper.ts";
import * as React from "react";

const UPDATE_INTERVAL_SEC = 1
const MAX_AGE_S = 86400; // 24 Hours
const MAX_AGE_MS = MAX_AGE_S * 1000;

const defaultSeries: ApexAxisChartSeries = [
    {
        name: "p-data",
        data: []
    },
    {
        name: "p-stored",
        data: []
    },
    {
        name: "p-solar",
        data: []
    }
]

export function GraphOverview({ state }: { state: StepUpdateMessage | undefined }) {
    const [lastUpdate, setLastUpdate] = useState<Dayjs | null>(null);
    const [maxBattery, setMaxBattery] = useState<number>(0);
    const pDataRef = useRef<{ x: number, y: number }[]>([]);
    const pStoredRef = useRef<{ x: number, y: number }[]>([]);
    const pSolarRef = useRef<{ x: number, y: number }[]>([]);

    const defaultOptions = useMemo<ApexOptions>(() => ({
        chart: {
            id: 'realtime',
            height: 350,
            animations: {
                enabled: true,
                dynamicAnimation: {
                    speed: 200
                }
            },
            toolbar: {
                show: false
            },
            zoom: {
                enabled: false
            }
        },
        annotations: {
            yaxis: [
                {
                    y: maxBattery,
                    borderColor: '#00E396',
                    label: {
                        position: "left",
                        offsetX: 70,
                        borderColor: '#00E396',
                        style: {
                            color: '#fff',
                            background: '#00E396'
                        },
                        text: 'Bat. Capacity'
                    }
                },
                {
                    y: 0,
                    borderColor: '#e30000',
                    label: {
                        position: "left",
                        offsetX: 25,
                        borderColor: '#e30000',
                        style: {
                            color: '#fff',
                            background: '#e30000'
                        },
                        text: '0 W'
                    }
                }
            ]
        },
        dataLabels: {
            enabled: false
        },
        stroke: {
            curve: 'monotoneCubic'
        },
        markers: {
            size: 0
        },
        xaxis: {
            type: 'datetime',
            range: dayjs.duration(1, "minute").asMilliseconds(),
        },
        yaxis: {
            decimalsInFloat: 0,
            forceNiceScale: true
        },
        legend: {
            show: true,
            onItemClick: {
                toggleDataSeries: false,
            },
            onItemHover: {
                highlightDataSeries: true
            }
        }
    }), [maxBattery]);

    useEffect(() => {
        if (!state?.time || state.p_delta == null) return;

        const now = dayjs();
        if (now.diff(lastUpdate, "seconds") < UPDATE_INTERVAL_SEC) {
            return;
        }
        setLastUpdate(now);

        const time = dayjs(state.time).add(2, "hours").toDate().getTime();
        const dataPoints = calculateMetricsFromState(state);

        if (dataPoints.battery.capacity != maxBattery) {
            setMaxBattery(dataPoints.battery.capacity);
        }

        const pDataPoint = { x: time, y: state.p_delta };
        const pStoredPoint = { x: time, y: dataPoints.battery.actual };
        const pSolarPoint = { x: time, y: dataPoints.solar };

        pDataRef.current.push(pDataPoint);
        pStoredRef.current.push(pStoredPoint);
        pSolarRef.current.push(pSolarPoint);

        const cutoff = time - MAX_AGE_MS;

        while (pDataRef.current.length && pDataRef.current[0].x < cutoff) {
            pDataRef.current.shift();
        }

        while (pStoredRef.current.length && pStoredRef.current[0].x < cutoff) {
            pStoredRef.current.shift();
        }

        while (pSolarRef.current.length && pSolarRef.current[0].x < cutoff) {
            pSolarRef.current.shift();
        }

        // Use ApexCharts.exec to update without re-render
        ApexCharts.exec("realtime", "updateSeries", [{
            name: "p-delta",
            data: [...pDataRef.current]
        }, {
            name: "p-stored",
            data: [...pStoredRef.current]
        }, {
            name: "p-solar",
            data: [...pSolarRef.current]
        }]);
    }, [lastUpdate, maxBattery, state]);

    function selectOnChange(e: React.ChangeEvent<HTMLSelectElement>) {
        e.preventDefault();

        const num = Number(e.target.value);
        ApexCharts.exec("realtime", "updateOptions", {
            xaxis: {
                range: num
            }
        });
    }

    return (
        <div className={"m-8"}>
            <h1 className={"text-3xl font-bold"}>Consumption Graph</h1>

            <select onChange={selectOnChange} id="countries" className="mt-3 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5">
                <option value={dayjs.duration(1, "minute").asMilliseconds()} selected>1 Minutes</option>
                <option value={dayjs.duration(5, "minutes").asMilliseconds()}>5 Minutes</option>
                <option value={dayjs.duration(15, "minutes").asMilliseconds()}>15 Minutes</option>
                <option value={dayjs.duration(30, "minutes").asMilliseconds()}>30 Minutes</option>
                <option value={dayjs.duration(60, "minutes").asMilliseconds()}>60 Minutes</option>
                <option value={dayjs.duration(24, "hours").asMilliseconds()}>24 Hours</option>
            </select>

            <div className="flex-col my-6 bg-white shadow-sm border border-slate-200 rounded-lg p-6">
                <div id="chart">
                    <ReactApexChart options={defaultOptions} series={defaultSeries} type={"line"} height={350}/>
                </div>
            </div>
        </div>
    );
}
