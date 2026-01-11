from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class WattTimeCarbonBase(SQLModel):
    """Base model for WattTime carbon intensity data."""
    region: str = Field(index=True, description="Region (Balancing Authority) abbreviation (e.g., 'CAISO_NORTH')")
    datetime_utc: datetime = Field(index=True, description="Time the data point was valid for (5 min steps)")
    percent: int = Field(description="Relative marginal carbon intensity (0-100)")
    moer: float = Field(description="Marginal Operating Emissions Rate (lbs CO2/MWh)")


class WattTimeCarbon(WattTimeCarbonBase, table=True):
    """Database table model for storing carbon intensity data."""
    id: Optional[int] = Field(default=None, primary_key=True)

    # Unique constraint to prevent duplicate entries for the same time and Region
    class Config:
        constraints = [("unique_region_datetime", "UNIQUE(region, datetime_utc)")]


class WattTimeCarbonCreate(WattTimeCarbonBase):
    """Model for creating new carbon entries (API input)."""
    pass


class WattTimeCarbonPublic(WattTimeCarbonBase):
    """Model for public API response."""
    id: int
