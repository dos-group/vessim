import mosaik
import mosaik.util

SIM_CONFIG = {
    'CSV': {
        'python': 'mosaik_csv:CSV',
        },
    'BatterySim': {
        'python': 'simulators.simple_battery_simulator:SimpleBatterySim',
        },
    'Collector': {
        'python': 'simulators.collector:Collector',
        },
    'PVController': {
        'python': 'simulators.pv_controller:PVController',
        },
    'Ecovisor': {
        'python': 'simulators.ecovisor:Ecovisor',
        },
}

START = '2014-01-01 14:08:00'
CONSUMPTION_DATA = '../resources/consumption.csv'
PV_DATA = '../resources/scaled_PV.csv'
CARBON_DATA = '../resources/example_carbon.csv'
END = 502

def main():
    world = mosaik.World(SIM_CONFIG) # type: ignore
    create_scenario(world)
    world.run(until=END,rt_factor=1)

def create_scenario(world):
    # Start simulators
    #consumption_sim = world.start('CSV', sim_start=START, datafile=CONSUMPTION_DATA)
    pv_sim = world.start('CSV', sim_start=START, datafile=PV_DATA)
    #consumption_controller = world.start('ConsumptionController')
    pv_controller = world.start('PVController')
    ecovisor = world.start('Ecovisor')
    collector = world.start('Collector')

    # Instantiate models
    #consumption_model = consumption_sim.Consumption()
    #consumption_agent = consumption_controller.ConsumptionAgent(kW_conversion_factor = 1)
    pv_model = pv_sim.PV()
    pv_agent = pv_controller.PVAgent(kW_conversion_factor = 1)
    ecovisor_model = ecovisor.EcovisorModel(carbon_datafile=CARBON_DATA)
    monitor = collector.Monitor()

    # Connect entities
    ## Consumer -> ConsumerAgent -> EcovisorModel:
    #world.connect(consumption_model,  ('P', 'consumption'))
    #world.connect( ecovisor_model, 'consumption', 'battery_charge_rate', 'battery_max_discharge')
    ## PVModel -> PVAgent -> EcovisorModel
    world.connect(pv_model, pv_agent, ('P', 'solar_power'))
    world.connect(pv_agent, ecovisor_model, 'solar_power')

    # Monitor
    world.connect(ecovisor_model, monitor,
                  'consumption',
                  'battery_charge_rate',
                  'battery_discharge_rate',
                  'battery_max_discharge',
                  'battery_charge_level',
                  'battery_delta',
                  'solar_power',
                  'grid_carbon',
                  'grid_power',
                  'total_carbon',
    )

if __name__ == '__main__':
    main()
