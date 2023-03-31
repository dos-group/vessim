import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Tuple, Dict

import mosaik
from mosaik.util import connect_many_to_one

from simulator.power_meter import PhysicalPowerMeter, AwsPowerMeter, LinearPowerModel

sim_config = {
    'CSV': {
        'python': 'mosaik_csv:CSV',
    },
    'Grid': {
        'python': 'mosaik_pandapower.simulator:Pandapower'
    },
    'ComputingSystemSim': {
        'python': 'simulator.computing_system:ComputingSystemSim',
    },
    'Collector': {
        'python': 'simulator.collector:Collector',
    },
    'PVController': {
        'python': 'simulator.pv_controller:PVController',
    },
    'CarbonController': {
        'python': 'simulator.carbon_controller:CarbonController',
    },
    'VirtualEnergySystem': {
        'python': 'simulator.virtual_energy_system:VirtualEnergySystem',
    },
}

START = '2014-01-01 00:00:00'
END = 10  # 30 * 24 * 3600  # 10 days
GRID_FILE = 'data/custom.json'  # "data/custom.json"  # 'data/demo_lv_grid.json'
PV_DATA = 'data/pv_10kw.csv'
CARBON_DATA = 'data/ger_ci_testing.csv'
BATTERY_MAX_DISCHARGE = 0.6
BATTERY_CAPACITY = 10 * 5 * 3600  # 10Ah * 5V * 3600 := Ws
BATTERY_INITIAL_CHARGE_LEVEL = BATTERY_CAPACITY * 0.7
BATTERY_C_RATE = 1/5

def main():
    random.seed(23)
    world = mosaik.World(sim_config) # type: ignore
    create_scenario_simple(world)
    world.run(until=END, print_progress=False, rt_factor=1)


def create_scenario_simple(world):
    #computing_system_sim = world.start('ComputingSystemSim')
    # aws_power_meter = AwsPowerMeter(instance_id="instance_id", power_model=LinearPowerModel(p_static=30, p_max=150))
    #raspi_power_meter = PhysicalPowerMeter()
    #computing_system = computing_system_sim.ComputingSystem(power_meters=[raspi_power_meter])

    # Carbon Sim from CSV dataset
    carbon_sim = world.start('CSV', sim_start=START, datafile=CARBON_DATA)
    carbon = carbon_sim.CarbonIntensity.create(1)[0]

    # Carbon Controller acts as a medium between carbon module and VES or
    # direct consumer since producer is only a CSV generator.
    carbon_controller = world.start('CarbonController')
    carbon_agent = carbon_controller.CarbonAgent(carbon_conversion_factor = 1)

    # PV Sim from CSV dataset
    pv_sim = world.start('CSV', sim_start=START, datafile=PV_DATA)
    pv = pv_sim.PV.create(1)[0]

    # PV Controller acts as medium between pv module and VES or direct consumer since producer is only a csv generator.
    pv_controller = world.start('PVController')
    pv_agent = pv_controller.PVAgent(kW_conversion_factor = 1)

    # VES Sim
    virtual_energy_system_sim = world.start('VirtualEnergySystem')
    virtual_energy_system = virtual_energy_system_sim.VirtualEnergySystemModel(
        carbon_datafile=CARBON_DATA,
        battery_capacity=BATTERY_CAPACITY,
        battery_charge_level=BATTERY_INITIAL_CHARGE_LEVEL,
        battery_max_discharge=BATTERY_MAX_DISCHARGE,
        battery_c_rate=BATTERY_C_RATE)

    # gridsim = world.start('Grid', step_size=60)
    # buses = filter(lambda e: e.type == 'PQBus', grid)
    # buses = {b.eid.split('-')[1]: b for b in buses}
    # world.connect(consumer, buses["node_a1"], ('P_out', 'P'))
    # world.connect(pvs[0], [e for e in grid if 'node' in e.eid][0], 'P')
    # nodes = [e for e in grid if e.type in ('RefBus, PQBus')]
    # load = [e for e in grid if e.eid == "0-load"][0]
    # ext_grid = [e for e in grid if e.type == "Ext_grid"][0]
    # lines = [e for e in grid if e.type == "Line"]

    collector = world.start('Collector')
    monitor = collector.Monitor()

    # Connect entities
    #world.connect(computing_system, monitor, 'p_cons')

    ## Carbon -> CarbonAgent -> VES
    world.connect(carbon, carbon_agent, ('CarbonIntensity', 'carbon_intensity'))
    world.connect(carbon_agent, virtual_energy_system, ('carbon_intensity', 'grid_carbon'))

    ## PV -> PVAgent -> VES
    world.connect(pv, pv_agent, ('P', 'solar_power'))
    world.connect(pv_agent, virtual_energy_system, 'solar_power')

    ## computing_system -> VES
    #world.connect(computing_system, virtual_energy_system, ('p_con', 'consumption'))

    world.connect(virtual_energy_system, monitor,
                'consumption',
                'battery_max_discharge',
                'battery_charge_level',
                'solar_power',
                'grid_carbon',
                'grid_power',
                'total_carbon',
    )

    # world.connect(load, monitor, 'p_mw')
    # world.connect(ext_grid, monitor, 'p_mw')
    # mosaik.util.connect_many_to_one(world, lines, monitor, 'loading_percent')


if __name__ == '__main__':
    main()
