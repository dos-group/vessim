import mosaik_api
from simulator.single_model_simulator import SingleModelSimulator
from simulator.simple_battery_model import SimpleBatteryModel
import redis
from redis.commands.json.path import Path
import docker


META = {
    'type': 'time-based',
    'models': {
        'VirtualEnergySystemModel': {
            'public': True,
            'params': [
                'battery_capacity',
                'battery_charge_level',
                'battery_max_discharge',
                'battery_c_rate',
            ],
            'attrs': [
                'consumption',
                'battery_max_discharge',
                'battery_charge_level',
                'solar_power',
                'grid_carbon',
                'grid_power',
                'total_carbon',
            ],
        },
    },
}


class VirtualEnergySystem(SingleModelSimulator):
    """Virtual Energy System (VES) simulator that executes the VES model."""

    def __init__(self):
        super().__init__(META, VirtualEnergySystemModel)


class VirtualEnergySystemModel:
    """A virtual energy system model.
    TODO: add more doc
    """

    def __init__(
        self,
        battery_capacity: float,
        battery_charge_level: float,
        battery_max_discharge: float,
        battery_c_rate: float,
    ):
        self.step_size = 1
        self.battery = SimpleBatteryModel(
            battery_capacity,
            battery_charge_level,
            battery_max_discharge,
            battery_c_rate,
            self.step_size,
        )
        self.battery_charge_level = self.battery.charge_level
        self.battery_charge_rate = 0.0
        self.battery_discharge_rate = 0.0
        self.battery_max_discharge = self.battery.max_discharge
        self.consumption = 0.0
        self.solar_power = 0.0
        self.grid_carbon = 0.0
        self.grid_power = 0.0
        self.total_carbon = 0.0
        self.container = {}

        # Initialize RedisDB and wait until ready
        self.client = docker.from_env()
        self.redis_container = self.client.containers.run(
            'redislabs/rejson:latest',
            detach=True,
            auto_remove=True,
            ports={6379: 6379},
            name="redis",
        )
        self.redis = redis.Redis(host='localhost', port=6379, db=0)
        while not self.is_redis_available():
            print("Waiting for RedisDB")
        self.send_redis_update()

    def __del__(self):
        self.redis_container.stop() # type: ignore

    def step(self) -> None:
        """Step the virtual energy system model."""
        self.get_redis_update()
        delta = self.solar_power - self.consumption

        # TODO to consumer for scenario
        # If carbon is low and battery does not have sufficient SOC, only charge battery
        if self.grid_carbon <= 250 and self.battery.soc() < self.battery_max_discharge:
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
        self.total_carbon = self.grid_carbon * self.grid_power
        self.send_redis_update()

    def send_redis_update(self) -> None:
        """Update Redis with the current data."""
        data_dict = {
            "solar_power": self.solar_power,
            "grid_power": self.grid_power,
            "grid_carbon": self.grid_carbon,
            "battery_discharge_rate": self.battery_discharge_rate,
            "battery_charge_level": self.battery_charge_level,
        }
        self.redis.mset(data_dict) # type: ignore
        self.redis.json().set('container', Path.root_path(), self.container)

    def get_redis_update(self) -> None:
        """Get data from Redis and update the current state."""
        key_dict = {"solar_power", "grid_power", "grid_carbon", "battery_charge_level"}
        data_dict = self.redis.mget(key_dict)
        data_dict = dict(zip(key_dict, data_dict))
        self.solar_power = float(data_dict["solar_power"]) # type: ignore
        self.grid_power = float(data_dict["grid_power"]) # type: ignore
        self.grid_carbon = float(data_dict["grid_carbon"]) # type: ignore
        self.battery_charge_level = float(data_dict["battery_charge_level"]) # type: ignore
        self.container = self.redis.json().get("container")

        # Compute total consumption of consumers
        d_values = self.container.values()
        consumption = 0
        for value in d_values:
            consumption += value
        self.consumption = consumption

    def is_redis_available(self) -> bool:
        """Check if Redis is available.

        Returns:
            bool: True if Redis is available, False otherwise.
        """
        try:
            self.redis.ping()
        except:
            return False
        return True


    # TODO adjust
    #def init_fastapi(self) -> FastAPI:
    #    app = FastAPI()

    #    @self.app.get('/number')
    #    def get_number():
    #        return {'number': int(self.redis.get('number'))}

    #    @self.app.put('/number/{number}')
    #    def set_number(number: int):
    #        self.redis.set('number', number)
    #        return {'number': number}

    #    @self.app.get('/word')
    #    def get_word():
    #        return {'word': self.redis.get('word').decode('utf-8')}

    #    @self.app.put('/word/{word}')
    #    def set_word(word: str):
    #        self.redis.set('word', word)
    #        return {'word': word}

    #    return app

def main():
    """Start the mosaik simulation."""
    return mosaik_api.start_simulation(VirtualEnergySystem())
