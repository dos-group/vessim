# Vessim

# Installation

Install the requirements in a virtual environment:

```
python3 -m venv venv              # create venv
. venv/bin/activate               # activate venv
pip3 install -r requirements.txt  # install dependencies
```
install & start docker `systemctl start docker`

start api server `python api_server.py`

start simulation `python mwe.py`

start consumer `python api_consumer.py`

## API usage
The API exposes the following endpoints via http.

The standard url is [localhost:8080/api/*](localhost:8080/api/*)

|Method|Endpoint|Parameter|
|------|--------|---------|
|GET|/api/solar_power|-|
|GET|/api/grid_power|-|
|GET|/api/grid_carbon|-|
|GET|/api/battery_discharge_rate|-|
|GET|/api/battery_charge_level|-|
|GET|/api/container_powercap|container_id:str|
|GET|/api/container_power|container_id:str|
|POST|/api/container_powercap|container_id:str, kW:float|
|POST|/api/battery_charge_level|kW:float|
|POST|/api/battery_max_discharge|kW:float|
