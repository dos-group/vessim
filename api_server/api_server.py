"""
This module contains the ApiServer.
Author: Henrik Nickel (Api integration)

"""
from fastapi import FastAPI, Form
import uvicorn
import redis
from redis.commands.json.path import Path
import os


class ApiServer:
    def __init__(self, host, port):
        self.battery_charge_rate = 0.0
        self.battery_discharge_rate = 0.0
        self.battery_charge_level = 0.0
        self.solar_power = 0.0
        self.grid_carbon = 0.0
        self.grid_power = 0.0
        self.container = {}
        self.redis = self.connect_to_redis('localhost',6379,0)
        #self.get_redis_update()
        self.run(host,port)

    
    def connect_to_redis(self,host,port,db):
        connected = False
        r = None
        while not connected:
            try:
                r = redis.Redis(host=host,port=port,db=db)
                connected = r.ping()
            except:
                print('No connection to RedisDB')
                pass
            
        return r

    def sim_get_solar_power(self) -> float:
        return self.solar_power

    def sim_get_grid_power(self) -> float:
        return self.grid_power

    def sim_get_grid_carbon(self) -> float:
        return self.grid_carbon

    def sim_get_battery_discharge_rate(self) -> float:
        return self.battery_discharge_rate

    def sim_get_battery_charge_level(self) -> float:
        return self.battery_charge_level

    def sim_get_container_powercap(self, container_id) -> float:
        return self.container[container_id]

    def sim_set_container_powercap(self, container_id, kW):
        self.container.update({container_id : kW})

    def sim_set_battery_charge_level(self, kW):
        self.battery_charge_level = kW

    def sim_set_battery_max_discharge(self, kW):
        self.battery_max_discharge = kW

    @property
    def app(self) -> FastAPI:
        app = FastAPI()

        #get_solar_power
        @app.get('/api/solar_power')
        async def get_solar_power():
            self.get_redis_update()
            kW = self.sim_get_solar_power()
            return { "kW" : kW}

        #get_grid_power
        @app.get('/api/grid_power')
        async def get_grid_power():
            self.get_redis_update()
            kW = self.sim_get_grid_power()
            return {'kW' : kW}

        #get_grid_carbon
        @app.get('/api/grid_carbon')
        async def get_grid_carbon():
            self.get_redis_update()
            co2 = self.sim_get_grid_carbon()
            return {'g*co_2/kW' : co2}

        #get_battery_discharge_rate
        @app.get('/api/battery_discharge_rate')
        async def battery_discharge_rate():
            self.get_redis_update()
            kW = self.sim_get_battery_discharge_rate()
            return {'kW' : kW}

        #get_battery_charge_level
        @app.get('/api/battery_charge_level')
        async def battery_charge_level():
            self.get_redis_update()
            kW = self.sim_get_battery_charge_level()
            return {'kW' : kW}

        #get_container_powercap
        @app.get('/api/container_powercap')
        async def container_powercap(container_id : str = Form(...)):
            self.get_redis_update()
            try:
                kW = self.sim_set_container_powercap(container_id)
            except:
                return {'An error occured!'}
            return {container_id + 'kW' : kW}

        #get_container_power
        @app.get('/api/container_power')
        async def container_power(container_id : str = Form(...)):
            self.get_redis_update()
            kW = self.sim_get_contaner_powercap(container_id)
            return { container_id + ' KW' : kW}

        #set container power cap
        @app.post("/api/container_powercap")
        async def container_powercap(container_id : str = Form(...), kW : float = Form(...)):
            try:
                self.sim_set_container_powercap(container_id, kW)
                self.send_redis_update()
            except:
                return {'An error occured!'}
            return{'Fine'}

        #set battery_charge_rate
        @app.post("/api/battery_charge_level")
        async def battery_charge_level(kW : float = Form(...)):
            try:
                self.sim_set_battery_charge_level(kW)
                self.send_redis_update()
            except:
                return {'An error occured!'}
            return{'Fine'}

        #set battery_max_discharge
        @app.post("/api/battery_max_discharge")
        async def battery_max_discharge(kW : float = Form(...)):
            try:
                self.sim_set_battery_max_discharge(kW)
                self.send_redis_update()
            except:
                return {'An error occured!'}
            return{'Fine'}

        #additional inti method if needed
        #app.on_event("startup")(self._init)
        return app

    def run(self,host, port = None) -> None:
        uvicorn.run(self.app, host=host or "127.0.0.1", port=port or 8080)

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
        print(data_dict)
        self.solar_power = float(data_dict["solar_power"])
        self.grid_power = float(data_dict["grid_power"])
        self.battery_discharge_rate = float(data_dict["battery_discharge_rate"])
        self.battery_charge_level = float(data_dict["battery_charge_level"])
        self.container = self.redis.json().get("container")
        self.grid_carbon = float(data_dict["grid_carbon"])
        
# For test purpose!

#app = lambda: a.app

if __name__ == '__main__':
    a = ApiServer('localhost',8080)
    #a.run()
