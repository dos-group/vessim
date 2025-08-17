import {SocketConnectionOverlay} from "./components/SocketConnectionOverlay.tsx";
import {useEffect, useRef} from "react";
import {socket} from "./lib/socketio.ts";
import type {StepUpdateMessage} from "./lib/types.ts";
import * as React from "react";
import {StatsOverview} from "./components/StatsOverview.tsx";
import {StatusBar} from "./components/StatusBar.tsx";
import {GraphOverview} from "./components/GraphOverview.tsx";
import {DetailView} from "./components/DetailView.tsx";

export const DATE_FORMAT = "DD.MM.YYYY HH:mm:ss UTC"

function App() {
    const ref = useRef<HTMLDivElement>(null);

    const [isConnected, setIsConnected] = React.useState<boolean>(socket.connected);
    const [data, setData] = React.useState<StepUpdateMessage | undefined>(undefined)

    useEffect(() => {
        function onConnect() {
            setTimeout(() => {
                ref.current?.classList.add("opacity-0", "pointer-events-none");
            }, 1500)

            console.log("Connected");
            setIsConnected(true);
        }

        function onDisconnect() {
            ref.current?.classList.remove("opacity-0", "pointer-events-none");

            setIsConnected(false);
        }

        function onStepUpdateEvent(e: StepUpdateMessage) {
            setData(e);
        }

        socket.on('connect', onConnect);
        socket.on('disconnect', onDisconnect);
        socket.on('step_update', onStepUpdateEvent);

        return () => {
            socket.off('connect', onConnect);
            socket.off('disconnect', onDisconnect);
            socket.off('step_update', onStepUpdateEvent);
        }
    }, []);

    return (
        <>
            <SocketConnectionOverlay ref={ref}/>

            <StatusBar connected={isConnected}/>

            <StatsOverview state={data}/>

            <GraphOverview state={data}/>

            <DetailView state={data}/>
        </>
    )
}

export default App
