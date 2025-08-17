import {io} from "socket.io-client";

export const SOCK_IO_URL = "ws://localhost:5000";

export const socket = io(SOCK_IO_URL, {
    transports: ["polling"]
});