"""
This module contains the Ecovisor model.
Author: Marvin Steinke

"""

from models.simple_battery_model import SimpleBatteryModel # type: ignore
from models.simple_energy_grid_model import SimpleEnergyGridModel # type: ignore
import redis
from redis.commands.json.path import Path
import docker

class EcovisorModel:
    def __init__(self, carbon_datafile, carbon_conversion_facor=1, sim_start=0, battery_capacity = 10, battery_charge_level = -1):
        self.battery = SimpleBatteryModel(battery_capacity, battery_charge_level)
        self.energy_grid = SimpleEnergyGridModel(carbon_datafile, carbon_conversion_facor, sim_start)
        self.battery_charge_level = self.battery.charge
        self.battery_charge_rate = 0.0
        self.battery_discharge_rate = 0.0
        self.battery_max_discharge = float('inf')
        self.consumption = 0.0
        self.solar_power = 0.0
        self.grid_carbon = 0.0
        self.grid_power = 0.0
        self.total_carbon = 0.0
        self.container = {}
        #Initalise RedisDB and wait until ready
        self.client = docker.from_env()
        self.redis_container = self.client.containers.run('redislabs/rejson:latest',detach=True,auto_remove=True,ports={6379:6379},name="redis" )
        self.redis = redis.Redis(host='localhost',port=6379,db=0)
        while not self.is_redis_available():
            print("Waiting for RedisDB")
        self.send_redis_update()

    #Cleans up after deleten of Obj
    def __del__(self):
        self.redis_container.stop()

    def step(self) -> None:
        self.get_redis_update()
        remaining = self.consumption - self.solar_power
        # excess (or equal) solar power
        if remaining <= 0:
            self.battery_discharge_rate = 0
        # solar power is insufficient -> use battery
        else:
            self.battery_discharge_rate = min(self.battery_max_discharge,
                                              self.battery_charge_level * 3600.0,
                                              remaining)
            remaining -= self.battery_discharge_rate
        self.grid_power = self.battery_charge_rate + remaining
        self.battery.delta = self.battery_charge_rate - self.battery_discharge_rate
        self.battery.step()
        self.battery_charge_level = self.battery.charge
        self.energy_grid.step()
        self.grid_carbon = self.energy_grid.carbon
        self.total_carbon = self.grid_carbon * self.grid_power
        self.send_redis_update()

    # methods to update redis data
    def send_redis_update(self) -> None:
        data_dict = {
            "solar_power" : self.solar_power,
            "grid_power" : self.grid_power,
            "grid_carbon" : self.grid_carbon,
            "battery_discharge_rate" : self.battery_discharge_rate,
            "battery_charge_level" : self.battery_charge_level,
        }
        self.redis.mset(data_dict)
        self.redis.json().set('container',Path.root_path(),self.container)
    
    def get_redis_update(self) -> None:
        key_dict = {"solar_power","grid_power","grid_carbon","battery_discharge_rate","battery_charge_level"}
        data_dict = self.redis.mget(key_dict)
        data_dict = dict(zip(key_dict,data_dict))        
        #print(data_dict)
        #self.solar_power = float(data_dict["solar_power"])
        #self.grid_power = float(data_dict["grid_power"])
        self.battery_discharge_rate = float(data_dict["battery_discharge_rate"])
        self.battery_charge_level = float(data_dict["battery_charge_level"])
        self.container = self.redis.json().get("container")
        #self.grid_carbon = float(data_dict["grid_carbon"])
        
        #compute total consumption of consumers
        d_values = self.container.values()
        consumption = 0
        for value in d_values:
            consumption = consumption + value
        self.consumption = consumption

    def is_redis_available(self):
    # ... get redis connection here, or pass it in. up to you.
        try:
            self.redis.ping()  # getting None returns None or throws an exception
        except:
            return False
        return True
