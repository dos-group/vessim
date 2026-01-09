from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class EntsoePriceBase(SQLModel):
	"""Base model for ENTSO-E price data."""
	zone: str = Field(index=True, description="Bidding zone code (e.g., 'DE_LU')")
	datetime_utc: datetime = Field(index=True, description="Start time of the interval")
	price_eur_per_mwh: float = Field(description="Day-ahead price in EUR/MWh")
	resolution_minutes: int = Field(default=15, description="Data resolution (PT15M)")


class EntsoePrice(EntsoePriceBase, table=True):
	"""Database table model for storing price data."""
	id: Optional[int] = Field(default=None, primary_key=True)

	# Unique constraint to prevent duplicate entries for the same time and zone
	class Config:
		constraints = [("unique_zone_datetime", "UNIQUE(zone, datetime_utc)")]


class EntsoePriceCreate(EntsoePriceBase):
	"""Model for creating new price entries (API input)."""
	pass


class EntsoePricePublic(EntsoePriceBase):
	"""Model for public API response."""
	id: int