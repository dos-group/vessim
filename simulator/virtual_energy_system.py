import mosaik_api
from simulator.single_model_simulator import SingleModelSimulator
from simulator.simple_battery_model import SimpleBatteryModel
from simulator.redis_docker import RedisDocker
from fastapi import FastAPI
from functools import partial
import json


META = {
    'type': 'time-based',
    'models': {
        'VirtualEnergySystemModel': {
            'public': True,
            'params': [
                'battery_capacity',
                'battery_soc',
                'battery_min_soc',
                'battery_c_rate',
                'db_host',
                'api_host'
            ],
            'attrs': [
                'consumption',
                'battery_min_soc',
                'battery_soc',
                'solar',
                'ci',
                'grid_power',
                'total_carbon',
            ],
        },
    },
}


class VirtualEnergySystem(SingleModelSimulator):
    """Virtual Energy System (VES) simulator that executes the VES model."""

    def __init__(self) -> None:
        super().__init__(META, VirtualEnergySystemModel)

    def finalize(self) -> None:
        """
        Overwrites mosaik_api.Simulator.finalize(). Stops the uvicorn server
        after the simulation has finished.
        """
        super().finalize()
        for _, model_instance in self.entities.items():
            model_instance.redis_docker.stop()


class VirtualEnergySystemModel:
    """A virtual energy system model.
    TODO: add more doc
    """

    def __init__(
        self,
        battery_capacity: float,
        battery_soc: float,
        battery_min_soc: float,
        battery_c_rate: float,
        db_host: str='127.0.0.1',
        api_host: str='127.0.0.1',
    ):
        # battery init
        self.step_size = 1
        self.battery = SimpleBatteryModel(
            battery_capacity,
            battery_soc,
            battery_min_soc,
            battery_c_rate,
            self.step_size,
        )
        # ves attributes
        self.battery_soc = self.battery.charge_level
        self.battery_min_soc = self.battery.max_discharge
        self.grid_charge = 0.0
        self.nodes = {}
        self.consumption = 0.0
        self.solar = 0.0
        self.ci = 0.0
        self.grid_power = 0.0
        self.total_carbon = 0.0
        # db & api
        self.redis_docker = RedisDocker(host=db_host)
        f_api = self.init_fastapi()
        self.redis_docker.run(f_api, host=api_host)


    def step(self) -> None:
        """Step the virtual energy system model."""
        #self.get_redis_update()
        delta = self.solar - self.consumption

        # TODO to consumer for scenario
        # If carbon is low and battery does not have sufficient SOC, only charge battery
        if self.ci <= 250 and self.battery.soc() < self.battery_min_soc:
            excess_power = self.battery.step(self.battery.max_charge_power)
            assert excess_power == 0
            delta -= self.battery.max_charge_power
        # Else charge or discharge depending on solar power (or resulting delta)
        else:
            max_charge_power = self.battery.max_charge_power
            battery_in = max(-max_charge_power, min(max_charge_power, delta))
            battery_out = self.battery.step(battery_in)
            delta += battery_out - battery_in

        self.grid_power = -delta
        self.total_carbon = self.ci * self.grid_power
        #self.send_redis_update()


    def init_fastapi(self) -> FastAPI:
        app = FastAPI()

        GET_route_attrs = {
            '/solar': 'solar',
            '/ci': 'ci',
            '/battery-soc': 'battery_soc',
            '/forecasts/solar': 'solar_forecast',
            '/forecasts/ci': 'ci_forecast'
        }
        self.init_GET_routes(GET_route_attrs, app)

        return app


    def init_GET_routes(self, GET_route_attrs: dict, app: FastAPI) -> None:
        """
        Initializes GET routes for a FastAPI app with the given route attributes and
        stores the initial values of the attributes in Redis key-value store.

        Args:
            GET_route_attrs: A dictionary containing the GET route as the key and
                the corresponding attribute as the value.
            app: A FastAPI app instance to which the GET routes will be added.

        Raises:
            AssertionError: If a Redis entry is not found for a given attribute or if
                the attribute value does not match the value stored in Redis.

        Example:
            GET_route_attrs = {
                "/route1": "attribute1",
                "/route2": "attribute2",
            }
            init_GET_routes(GET_route_attrs, app)
        """

        # store attributes and its initial values in Redis key-value store
        redis_content = {entry: getattr(self, entry) for entry in GET_route_attrs.values() if hasattr(self, entry)}
        self.redis_docker.redis.mset(redis_content)

        # FastAPI hook function for all GET routes to retrieve data from Redis
        # and ensure it matches the attribute values
        def get_data(attr):
            redis_entry = self.redis_docker.redis.get(attr)
            assert redis_entry != None
            value = None
            # entries may either be of primitive type or json
            try:
                value = json.loads(redis_entry)
            except json.JSONDecodeError:
                # cast redis entry the type of its corresponding attribute in this class
                value = type(getattr(self, attr))(redis_entry)
            assert getattr(self, attr) == value
            return value

        # connect get_data function to FastAPI for every route
        for route, attr in GET_route_attrs:
            if hasattr(self, attr):
                app.get(route)(partial(get_data, attr))


    def print_redis(self):
        """
        Debugging function that simply prints all entries of the redis db.
        """

        r = self.redis_docker.redis
        # Start the SCAN iterator
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor)
            for key in keys:
                # Check the type of the key
                key_type = r.type(key)

                # Retrieve the value according to the key type
                if key_type == b'string':
                    value = r.get(key)
                elif key_type == b'hash':
                    value = r.hgetall(key)
                elif key_type == b'list':
                    value = r.lrange(key, 0, -1)
                elif key_type == b'set':
                    value = r.smembers(key)
                elif key_type == b'zset':
                    value = r.zrange(key, 0, -1, withscores=True)
                else:
                    value = None

                print(f"Key: {key}, Type: {key_type}, Value: {value}")

            if cursor == 0:
                break

def main():
    """Start the mosaik simulation."""
    return mosaik_api.start_simulation(VirtualEnergySystem())
