# VESSIM Node API Server

This repository contains an API server designed to run on different types of
nodes, specifically tailored for a Raspberry Pi and a Linux node. The project
is designed to be integrated into the VESSIM environment.

## Description

The API server is implemented as two distinct classes - `RpiNodeApiServer` and
`VirtualNodeApiServer` - both inheriting from the abstract `FastApiServer`
class.

The `RpiNodeApiServer` is specifically tailored for a Raspberry Pi, using
dynamic voltage and frequency scaling (DVFS) for power management, while the
`VirtualNodeApiServer` is designed to run on a Linux node, using `cpulimit` for
process CPU usage limitation. Both implementations allow the control of power
modes via API calls.

## Setup
### Raspberry Pi Node Setup

For setting up the project on a Raspberry Pi, follow the below instructions:

1. SSH into your Raspberry Pi:
```bash
ssh pi@raspberrypi
```

2. Update and upgrade your Pi:
```bash
sudo apt update && sudo apt upgrade
```

3. Install necessary dependencies:
```bash
sudo apt install git vim python3-pip i2c-tools
```

4. Clone the repository:
```bash
git clone https://github.com/dos-group/vessim/
```

5. Navigate to the example_node directory and install Python dependencies:
```bash
cd vessim/example_node/rpi
sudo pip install -r requirements.txt
```

6. Execute initialization script:
```bash
sudo sh init.sh
```

7. Reboot your Raspberry Pi:
```bash
sudo reboot
```

## Usage

Once installed and set up, you can start the API server. It will start
listening for incoming HTTP requests on the defined host and port.

The server exposes the following endpoints:

- `PUT /power_mode`: Set the power mode for the server. The available power modes are `power-saving`, `normal`, and `high performance`.
- `GET /power_mode`: Retrieve the current power mode of the server.
- `GET /power`: Retrieve the current power usage of the node.
- `PUT /pid`: Set the PID of a process for virtual nodes to limit its CPU usage. For the Raspberry Pi node, this operation is not supported, as DVFS is used instead of `cpulimit`.
