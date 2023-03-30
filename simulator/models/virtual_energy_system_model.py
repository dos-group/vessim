"""
This module contains the Virtual Energy System Model.
Author: Marvin Steinke, Henrik Nickel, Philipp Wiesner

"""

from models.simple_battery_model import SimpleBatteryModel
from models.carbon_intensity_model import CarbonIntensityModel
import redis
from redis.commands.json.path import Path
import docker

class VirtualEnergySystemModel:
    def __init__(self, battery_capacity, battery_charge_level, battery_max_discharge, battery_c_rate):
        self.step_size = 1
        self.battery = SimpleBatteryModel(battery_capacity, battery_charge_level, battery_max_discharge, battery_c_rate, self.step_size)
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

        # Initalise RedisDB and wait until ready
        self.client = docker.from_env()
        self.redis_container = self.client.containers.run('redislabs/rejson:latest',detach=True,auto_remove=True,ports={6379:6379},name="redis" )
        self.redis = redis.Redis(host='localhost',port=6379,db=0)
        while not self.is_redis_available():
            print("Waiting for RedisDB")
        self.send_redis_update()

    # Cleans up after deleten of Obj
    def __del__(self):
        self.redis_container.stop() # type: ignore

    def step(self) -> None:
        self.get_redis_update()
        delta = self.solar_power - self.consumption

        # if carbon is low and battery does not have sufficient soc -> only charge battery
        if self.grid_carbon <= 250 and self.battery.soc() < self.battery_max_discharge:
            excess_power = self.battery.step(self.battery.max_charge_power)
            assert excess_power == 0
            delta -= self.battery.max_charge_power
        # else charge or discharge depending on solar power (or resulting delta)
        else:
            max_charge_power = self.battery.max_charge_power
            battery_in = max(-max_charge_power, min(max_charge_power, delta))
            battery_out = self.battery.step(battery_in)
            delta += battery_out - battery_in

        self.grid_power = -delta
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
        self.redis.mset(data_dict) # type: ignore
        self.redis.json().set('container',Path.root_path(),self.container)

    def get_redis_update(self) -> None:
        key_dict = {"solar_power", "grid_power", "grid_carbon", "battery_charge_level"}
        data_dict = self.redis.mget(key_dict)
        data_dict = dict(zip(key_dict,data_dict))
        #print(data_dict)
        self.solar_power = float(data_dict["solar_power"]) # type: ignore
        self.grid_power = float(data_dict["grid_power"]) # type: ignore
        self.grid_carbon = float(data_dict["grid_carbon"]) # type: ignore
        self.battery_charge_level = float(data_dict["battery_charge_level"]) # type: ignore
        self.container = self.redis.json().get("container")

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
