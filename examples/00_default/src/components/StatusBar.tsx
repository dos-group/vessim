import {SOCK_IO_URL, socket} from "../lib/socketio.ts";
import * as React from "react";
import {useEffect} from "react";
import dayjs from "dayjs";
import {BsWifi, BsWifiOff} from "react-icons/bs";
import {DATE_FORMAT} from "../App.tsx";

export function StatusBar({connected}: {connected: boolean}) {
    const [ping, setPing] = React.useState<number>(-1);
    const [time, setTime] = React.useState<string>(dayjs.utc().format(DATE_FORMAT));

    useEffect(() => {
        function calculatePing() {
            const start = performance.now();
            socket.emit("ping", () => {
                const diff = performance.now() - start;
                setPing(diff);
            });
        }

        calculatePing();
        const pingHandle = setInterval(() => {
            calculatePing();
        }, 5_000);

        const timeHandle = setInterval(() => {
            setTime(dayjs.utc().format(DATE_FORMAT))
        }, 1_000)

        return () => {
            clearInterval(pingHandle);
            clearInterval(timeHandle);
        }
    }, []);
    
    return (
        <div className={"fixed top-0 left-0 flex justify-between w-full p-2 bg-gray-200 border-b border-b-gray-300 z-[100]"}>
            <div className={"flex"}>
                <h3>{time}</h3>
                <span className={"mx-4 text-gray-400"}>|</span>

                {connected ?
                <span className={"flex"}>
                    <BsWifi size={25} className={"text-green-700 h-full mr-4"}/>
                    Latency: {ping} ms
                </span>
                    :
                <span className={"flex"}>
                    <BsWifiOff size={25} className={"text-red-700 h-full mr-4"}/>
                </span>
                }
            </div>

            <div>
                <pre>{SOCK_IO_URL}</pre>
            </div>


        </div>
    )
}