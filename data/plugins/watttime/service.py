import logging
import os
from http.client import responses
from datetime import datetime, timezone
from typing import Optional, Dict

import requests
import pandas as pd

WATTIME_URL = 'https://api.watttime.org/'

class WattTimeService:
    """Handles communication with the WattTime API."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username
        self.password = password
        self.token = None
        self.logger = logging.getLogger(__name__)
        
        if self.username and self.password:
            self.login()
        else:
            self.logger.warning("⚠️ WattTime credentials not provided. API calls requiring auth will fail.")

    def login(self) -> bool:
        """Authenticate with WattTime and retrieve a token."""
        try:
            response = requests.get(
                WATTIME_URL + 'login',
                auth=(self.username, self.password)
            )
            if response.ok:
                self.token = response.json().get('token')
                self.logger.info("✅ WattTime login successful")
                return True
            else:
                self.logger.error(f"❌ WattTime login failed: {response.status_code} {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"❌ WattTime login error: {e}")
            return False

    def get_headers(self) -> Dict[str, str]:
        """Return headers with the authorization token."""
        if not self.token:
            # Try to login again if token is missing
            if not self.login():
                raise ValueError("WattTime authentication failed or missing credentials.")
        return {'Authorization': f'Bearer {self.token}'}

    def register(self, username: str, password: str, email: str, *, org: Optional[str]=None) -> bool:
        """Register a new user."""
        params = {'username': username,
                  'password': password,
                  'email': email,
                  'org': org}
        response = requests.post(WATTIME_URL+'register', json=params)
        if response.ok:
            self.logger.info(f"WattTime registration successful: User {username} created")
            return True
        else:
            self.logger.error(f"WattTime registration failed: {response.status_code} {responses[response.status_code]} {response.json()}")
            return False

    def get_region_from_loc(self, signal_type: str, latitude: float, longitude: float) -> Optional[str]:
        """
        Determine the Region (Balancing Authority) for a given location (latitude, longitude).
        """
        url = WATTIME_URL + 'v3/region-from-loc'
        params = {
            'signal_type': signal_type,
            'latitude': latitude,
            'longitude': longitude
        }

        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.ok:
                data = response.json()
                return data.get('region')
            else:
                self.logger.error(f"WattTime region lookup failed: {response.status_code} {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"WattTime API error (region lookup): {e}")
            return None

    def get_historical_data(self, region: str, start_time: datetime, end_time: datetime, signal_type: str = 'co2_moer') -> pd.DataFrame:
        """
        Fetch historical carbon intensity data for a specific region (Balancing Authority).        """
        url = WATTIME_URL + 'v3/historical'

        # Ensure start_time is UTC-aware
        if start_time.tzinfo is None:
            start_time_utc = start_time.replace(tzinfo=timezone.utc)
        else:
            start_time_utc = start_time.astimezone(timezone.utc)

        # Ensure end_time is UTC-aware
        if end_time.tzinfo is None:
            end_time_utc = end_time.replace(tzinfo=timezone.utc)
        else:
            end_time_utc = end_time.astimezone(timezone.utc)

        params = {
            'region': region,
            'start': start_time_utc.replace(microsecond=0).isoformat(),
            'end': end_time_utc.replace(microsecond=0).isoformat(),
            'signal_type': signal_type
        }
        
        try:
            self.logger.info(f"Fetching WattTime data for {region} from {params['start']} to {params['end']}")
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.ok:
                data = response.json()
                df = pd.DataFrame(data['data'])
                if not df.empty and 'point_time' in df.columns:
                    df['datetime_utc'] = pd.to_datetime(df['point_time'])
                return df
            else:
                self.logger.error(f"WattTime data fetch failed: {response.status_code} {response.text}")
                response.raise_for_status()
        except Exception as e:
            self.logger.error(f"WattTime API error: {e}")
            raise

    def check_connection(self) -> bool:
        """Checks if the API is reachable and credentials are valid."""
        if not self.token:
             return self.login()
        return True
