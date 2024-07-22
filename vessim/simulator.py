import vessim as vs
from windpowerlib import WindTurbine, ModelChain
import pandas as pd
import numpy as np

# Define Enviroment (random Day)
environment = vs.Environment(sim_start="2024-07-17")

# Data Center Stats 
data_center_load = 120000000  # 120 MW load
data_center = vs.Actor(
    name="data_center",
    signal=vs.MockSignal(value=data_center_load)  
)

# Wind Data init, used predefined from windpowerlib
turbine_data = {
    'turbine_type': 'E-126/4200',  # Enercon E-126/4200 wind turbine
    'hub_height': 135  
}

# Windpark with var Numbers (here 30)
number_turbines = 30  # 30 Turbines from type E-126/4200
wind_turbines = [WindTurbine(**turbine_data) for _ in range(number_turbines)]

# Random weather conditions within 24 Hours (1 Day)
hours = 24

wind_speed = pd.Series(np.random.uniform(5, 15, hours), index=pd.date_range(start='2024-07-17', periods=hours, freq='H'))  #Random wind speed between 5-15 km/h
temperature = pd.Series(np.random.uniform(10, 20, hours), index=pd.date_range(start='2024-07-17', periods=hours, freq='H'))  # Random temperature between 10-15
roughness = pd.Series([0.1] * hours, index=pd.date_range(start='2024-07-17', periods=hours, freq='H'))  # roughness (not really necessary for the sim right now)

#the numbers are common reference heights
weather = pd.DataFrame({            # using pandas
    ('wind_speed', 10): wind_speed, # wind speed defined at height 10 m
    ('temperature', 2): temperature,    #temperatur at 2 m 
    ('roughness_length', 0): roughness
})

# Getting power output from the turbines (using windpowerlib)
wind_power_output_all = sum(ModelChain(turbine).run_model(weather).power_output for turbine in wind_turbines)


# Calculate the delta (for simulation) (Wind Turbine Power - Data Center Load)
delta = wind_power_output_all - data_center_load

# Integrating turbines as actors
wind_turbine_actor = vs.Actor(
    name="wind_turbine",
    signal=vs.HistoricalSignal(wind_power_output_all)
)



# delta as actor too
delta_actor = vs.Actor(
    name="delta",
    signal=vs.HistoricalSignal(delta)
)


#From the example from the vessim github

# Monitor for collecting results
monitor = vs.Monitor()

# Add microgrid components to the environment
environment.add_microgrid(
    actors=[
        data_center,
        wind_turbine_actor,
        delta_actor
    ],
    controllers=[monitor],
    step_size=3600,  # Schrittgröße in Sekunden für stündliche Daten
)

# run simulation for a day
environment.run(until=24 * 3600)  # 24 Stunden
monitor.to_csv("result.csv")

