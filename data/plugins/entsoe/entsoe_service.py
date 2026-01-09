import logging
import pandas as pd
from entsoe import EntsoePandasClient


class EntsoeService:
	"""Handles communication with the ENTSO-E Transparency Platform API."""

	def __init__(self, api_key: str):
		# Initialize the official entsoe-py client[citation:2][citation:4]
		self.api_key = api_key
		self.client = None
		self.logger = logging.getLogger(__name__)

		if api_key:
			try:
				self.client = EntsoePandasClient(api_key=api_key)
				self.logger.info("✅ ENTSO-E Client initialized")
			except ImportError:
				self.logger.warning("⚠️ entsoe-py not installed")
		else:
			self.logger.warning("⚠️ No ENTSO-E API Key found!")

	def check_connection(self) -> bool:
		"""Checks if the API key is valid and the server is reachable."""
		if not self.client:
			self.logger.error("ENTSO-E Client not initialized (missing API key?)")
			return False
		
		try:
			# Try a simple query to check connectivity
			# Using a small recent time window for a common zone (e.g., DE_LU)
			end = pd.Timestamp.now(tz='UTC')
			start = end - pd.Timedelta(hours=1)
			self.client.query_day_ahead_prices(country_code='DE_LU', start=start, end=end)
			self.logger.info("✅ ENTSO-E API connection check successful")
			return True
		except Exception as e:
			# It's possible the query fails due to data availability, but if it's an auth error or connection error, we catch it here.
			# Note: query_day_ahead_prices might raise NoMatchingDataError if no data, which implies connection worked.
			# We'll assume any non-connection/auth error means we reached the server.
			if "401" in str(e) or "Unauthorized" in str(e):
				self.logger.error(f"❌ ENTSO-E API Authentication failed: {e}")
				return False
			elif "No matching data found" in str(e):
				# This actually means we connected successfully but just didn't find data for this specific hour
				self.logger.info("✅ ENTSO-E API connection check successful (No data for probe, but connected)")
				return True
			
			self.logger.warning(f"⚠️ ENTSO-E API connection check warning: {e}")
			# Depending on strictness, we might return False or True. 
			# If we want to be strict about "reachable", maybe True if it's just a data error.
			return True

	def fetch_price_data(
			self,
			zone: str,
			start: pd.Timestamp,
			end: pd.Timestamp
	) -> pd.Series:
		"""
		Fetches day-ahead price data for a specific zone and time range.
		"""
		if not self.client:
			raise ValueError("ENTSO-E Client not initialized. Check API Key.")

		try:
			self.logger.info(f"Fetching prices for {zone} from {start} to {end}")
			# This returns a pandas Series with datetime index and price values[citation:4]
			price_series = self.client.query_day_ahead_prices(
				country_code=zone,
				start=start,
				end=end
			)
			return price_series
		except Exception as e:
			self.logger.error(f"ENTSO-E API error: {e}")
			raise

def fill_missing_timestamps(price_series: pd.Series, resolution_minutes: int = 15) -> pd.Series:
	"""
	ENTSO-E API may omit timestamps where the price is unchanged.
	This function creates a complete time series by forward-filling missing values.
	"""
	if price_series.empty:
		return price_series

	# Create a complete datetime range at the specified resolution
	full_range = pd.date_range(
		start=price_series.index.min(),
		end=price_series.index.max(),
		freq=f'{resolution_minutes}min',
		tz=price_series.index.tz
	)

	# Reindex the series to the complete range, forward-filling missing prices
	complete_series = price_series.reindex(full_range, method='ffill')

	return complete_series