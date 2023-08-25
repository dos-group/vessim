from datetime import timedelta
import pandas as pd

# use importlib.resources for Python >=3.9 (which includes the 'files' function)
# for Python 3.8 use the external importlib_resources to backfill this functionality
try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import files

# Use importlib.resources to get the absolute path to resources inside examples module
resources = files('examples')
SOLAR_DATA_FILE = resources / 'data/weather_berlin_2021-06.csv'
CARBON_DATA_FILE = resources / 'data/carbon_intensity.csv'

def load_solar_data(sqm: float) -> pd.Series:
    irradiance_data = pd.read_csv(SOLAR_DATA_FILE, index_col="time",
                                  parse_dates=True)["solar"]
    irradiance_data.index -= timedelta(days=365)
    production_data = irradiance_data * sqm * .17  # W/m^2 * m^2 = W
    return production_data.astype(float)

def load_carbon_data() -> pd.DataFrame:
    return pd.read_csv(CARBON_DATA_FILE, index_col="time", parse_dates=True)
