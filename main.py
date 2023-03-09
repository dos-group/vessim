import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Tuple, Dict

import mosaik
from mosaik.util import connect_many_to_one

from simulator.power_meter import PhysicalPowerMeter, AwsPowerMeter

sim_config = {
    'Grid': {
        'python': 'mosaik_pandapower.simulator:Pandapower'
    },
    'ComputingSystemSim': {
        'python': 'simulator.computing_system:ComputingSystemSim',
    },
    'Collector': {
        'python': 'simulator.collector:Collector',
    },
}

START = '2014-01-01 00:00:00'
END = 300  # 30 * 24 * 3600  # 10 days
GRID_FILE = 'data/custom.json'  # "data/custom.json"  # 'data/demo_lv_grid.json'
PV_DATA = "pv_10kw.csv"


def main():
    random.seed(23)
    world = mosaik.World(sim_config)
    create_scenario_simple(world)
    world.run(until=END, print_progress=False)  # , rt_factor=1/600


def create_scenario_simple(world):
    pvsim = world.start('CSV', sim_start=START, datafile=PV_DATA)
    computing_system_sim = world.start('ComputingSystemSim')
    collector = world.start('Collector')

    aws_power_meter = AwsPowerMeter()
    raspi_power_meter = PhysicalPowerMeter()
    computing_system = computing_system_sim.ComputingSystem(power_meters=[aws_power_meter, raspi_power_meter])
    monitor = collector.Monitor()

    world.connect(computing_system, monitor, 'p_cons')


def create_scenario(world):
    # Start simulators
    gridsim = world.start('Grid', step_size=60)
    computing_system_sim = world.start('ComputingSystemSim')
    # pvsim = world.start('CSV', sim_start=START, datafile=PV_DATA)
    collector = world.start('Collector')

    # Instantiate models
    grid = gridsim.Grid(gridfile=GRID_FILE).children
    computing_system = computing_system_sim.ComputingSystem(power_monitors=[PowerMonitor(p=10), PowerMonitor(p=20)])
    # pvs = pvsim.PV.create(1)
    monitor = collector.Monitor()

    # Connect entities
    #buses = filter(lambda e: e.type == 'PQBus', grid)
    #buses = {b.eid.split('-')[1]: b for b in buses}
    #world.connect(consumer, buses["node_a1"], ('P_out', 'P'))

    #world.connect(pvs[0], [e for e in grid if 'node' in e.eid][0], 'P')

    #nodes = [e for e in grid if e.type in ('RefBus, PQBus')]

    load = [e for e in grid if e.eid == "0-load"][0]
    ext_grid = [e for e in grid if e.type == "Ext_grid"][0]
    lines = [e for e in grid if e.type == "Line"]

    world.connect(load, monitor, 'p_mw')
    world.connect(ext_grid, monitor, 'p_mw')
    mosaik.util.connect_many_to_one(world, lines, monitor, 'loading_percent')


if __name__ == '__main__':
    main()
