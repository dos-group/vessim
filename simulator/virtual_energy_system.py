import mosaik_api
from simulator.single_model_simulator import SingleModelSimulator
from simulator.simple_battery_model import SimpleBatteryModel
from simulator.redis_docker import RedisDocker
from fastapi import FastAPI
import threading


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
        self.consumption = 0.0
        self.solar = 0.0
        self.ci = 0.0
        self.grid_power = 0.0
        self.total_carbon = 0.0
        # db & api
        self.sim_progress = 0
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

        @app.get('/solar')
        def get_solar():
            redis_solar = self.redis_docker.redis.get('solar')
            assert redis_solar != None
            redis_solar = float(redis_solar)
            assert self.solar == redis_solar
            return {'solar': self.solar}

        @app.put('/solar/{solar}')
        def set_solar(solar: float):
            self.solar = solar
            self.redis_docker.redis.set('solar', solar)
            return {'solar': solar}

        @app.get('/word')
        def get_word():
            return {'word': self.redis_docker.redis.get('word').decode('utf-8')}

        @app.put('/word/{word}')
        def set_word(word: str):
            self.redis_docker.redis.set('word', word)
            return {'word': word}

        return app

def main():
    """Start the mosaik simulation."""
    return mosaik_api.start_simulation(VirtualEnergySystem())
