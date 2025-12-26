import vessim as vs

# 1. StaticSignal
# A signal that always returns the same value. Useful for testing or constant loads.
static_signal = vs.StaticSignal(value=42)
print(f"Static signal value: {static_signal.now(0)}")


# 2. Trace (Historical Data)
# Vessim includes datasets for solar irradiance and carbon intensity.
# You can load them into a Trace signal.

# Example: Solar irradiance in Berlin from the 'solcast2022_global' dataset.
# This dataset contains 5-minute interval data.
solar_signal = vs.Trace.load(
    dataset="solcast2022_global",
    column="Berlin",
    params={"scale": 1000}  # Scale the normalized (0-1) data to 1000W peak
)

print(f"Solar signal at start: {solar_signal.now('2022-06-15 12:00')}")

# Example: Carbon intensity in California from 'watttime2023_caiso-north'
carbon_signal = vs.Trace.load(
    dataset="watttime2023_caiso-north",
    column="Caiso_North"  # Marginal Operating Emissions Rate
)
print(f"Carbon intensity at start: {carbon_signal.now('2023-06-15 00:00')}")

# You can also use your own data by creating a Trace from a pandas Series or DataFrame.
# import pandas as pd
# data = pd.Series([1, 2, 3], index=pd.date_range("2022-01-01", periods=3, freq="5min"))
# custom_signal = vs.Trace(data)
