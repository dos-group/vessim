import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter
from fastapi import Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from dotenv import load_dotenv, set_key

from core.database import get_managed_session
from .service import WattTimeService
from .models import WattTimeCarbon, WattTimeCarbonCreate, WattTimeCarbonPublic

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# Each plugin has its own router
router = APIRouter(prefix="/watttime", tags=["watttime"])

watttime_service = WattTimeService(
    username=os.environ.get("WATTTIME_USERNAME"),
    password=os.environ.get("WATTTIME_PASSWORD")
)

def startup():
    """
    Perform startup checks for the WattTime plugin.
    If credentials are missing or invalid, prompt for registration/login via terminal.
    """
    logging.info("Checking WattTime API connection...")
    
    if not watttime_service.check_connection():
        logging.warning("WattTime connection failed. Starting interactive setup... (maybe press enter twice for continuing)")
        _interactive_setup()
    else:
        logging.info("✅ WattTime connection verified.")

def _interactive_setup():
    """
    Interactive terminal setup for WattTime credentials.
    """
    print("\n--- WattTime Setup ---")
    print("Existing credentials failed or are missing.")
    
    while True:
        choice = input("Do you want to (L)ogin with existing credentials or (R)egister a new account? [L/R]: ").strip().upper()
        
        if choice == 'L':
            username = input("Username: ").strip()
            password = input("Password: ").strip()
            
            # Test login
            temp_service = WattTimeService(username=username, password=password)
            if temp_service.login():
                print("Login successful!")
                _save_credentials(username, password)
                # Update the global service instance
                watttime_service.username = username
                watttime_service.password = password
                watttime_service.token = temp_service.token
                break
            else:
                print("Login failed. Please try again.")
        
        elif choice == 'R':
            username = input("Desired Username: ").strip()
            password = input("Desired Password: ").strip()
            email = input("Email: ").strip()
            org = input("Organization (optional, press Enter to skip): ").strip() or None
            
            # Attempt registration
            temp_service = WattTimeService()
            if temp_service.register(username, password, email, org=org):
                print("Registration successful!")
                # Automatically try to login after registration
                temp_service.username = username
                temp_service.password = password
                if temp_service.login():
                    print("Login successful!")
                    _save_credentials(username, password)
                    # Update the global service instance
                    watttime_service.username = username
                    watttime_service.password = password
                    watttime_service.token = temp_service.token
                    break
                else:
                    print("Login failed after registration. Please check your credentials.")
            else:
                print("Registration failed. Please try again.")
        
        else:
            print("Invalid choice. Please enter 'L' or 'R'.")

def _save_credentials(username, password):
    """
    Ask user if they want to save credentials to .env and do so if confirmed.
    """
    save = input("Do you want to save these credentials to the .env file? [y/N]: ").strip().lower()
    if save == 'y':
        try:
            if not os.path.exists(dotenv_path):
                with open(dotenv_path, 'w') as f:
                    f.write("")
            
            set_key(dotenv_path, "WATTTIME_USERNAME", username)
            set_key(dotenv_path, "WATTTIME_PASSWORD", password)
            print(f"Credentials saved to {dotenv_path}")
        except Exception as e:
            logging.error(f"Failed to save credentials to .env: {e}")
            print(f"Error saving credentials: {e}")


# --- API Endpoints ---

@router.get("/")
def get_overview():
    """Returns an overview of available endpoints for the WattTime plugin."""
    return {
        "message": "Welcome to the WattTime API. Available endpoints:",
        "endpoints": [
            {"path": "/carbon/", "method": "GET", "description": "Retrieve WattTime carbon intensity data for a given Region (region) and time range. Fetches from cache or WattTime API."},
            {"path": "/carbon/", "method": "POST", "description": "Manually store a single WattTime carbon data point in the cache."},
            {"path": "/carbon/fetch-range/", "method": "POST", "description": "Trigger a background task to fetch and store a range of WattTime carbon data."},
            {"path": "/region-from-loc/", "method": "GET", "description": "Get the Region (Balancing Authority) for a given latitude and longitude."},
            {"path": "/health", "method": "GET", "description": "Check the health status of the WattTime plugin."}
        ]
    }


@router.post("/carbon/", response_model=WattTimeCarbonPublic)
def create_carbon_entry(
        carbon: WattTimeCarbonCreate,
        session: Session = Depends(get_managed_session)
):
    """Store a single carbon data point in the cache. Useful for manual updates."""
    db_carbon = WattTimeCarbon.model_validate(carbon)
    session.add(db_carbon)
    session.commit()
    session.refresh(db_carbon)
    return db_carbon


@router.get("/carbon/", response_model=List[WattTimeCarbonPublic])
def get_carbon_data(
        region: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        session: Session = Depends(get_managed_session)
):
    """
    Main endpoint for Vessim to retrieve carbon data.
    Returns cached data; if missing, fetches from WattTime.
    """
    # Set default end time if not provided
    if end_time is None:
        end_time = start_time + timedelta(days=1)

    # 1. Check cache first
    statement = select(WattTimeCarbon).where(
        WattTimeCarbon.region == region,
        WattTimeCarbon.datetime_utc >= start_time,
        WattTimeCarbon.datetime_utc <= end_time
    ).order_by(WattTimeCarbon.datetime_utc)

    cached_results = session.exec(statement).all()

    if cached_results:
        # Check if we have a complete set for the requested range
        # WattTime data is typically 5-minute resolution, but can vary.
        # We'll use a simple heuristic or just return what we have if it looks substantial.
        # For now, let's assume if we have some data, we return it.
        # A more robust check would calculate expected points based on resolution.
        if len(cached_results) > 0:
             return cached_results

    # 2. If cache is insufficient, fetch from WattTime
    try:
        # Fetch historical data from WattTime
        df = watttime_service.get_historical_data(region, start_time, end_time, signal_type='co2_moer')

        if df.empty:
             return []

        # Store in database
        results = []
        for _, row in df.iterrows():
            # WattTime API returns fields like 'percent', 'moer', 'point_time'
            # We need to map them to our model
            carbon_entry = WattTimeCarbon(
                region=region,
                datetime_utc=row['datetime_utc'].to_pydatetime(),
                percent=row.get('percent', 0),
                moer=row.get('moer', 0.0)
            )
            # Use merge to handle duplicates gracefully
            session.merge(carbon_entry)
            results.append(carbon_entry)

        session.commit()

        # Return the newly fetched data (re-query to ensure order and consistency)
        statement = select(WattTimeCarbon).where(
            WattTimeCarbon.region == region,
            WattTimeCarbon.datetime_utc >= start_time,
            WattTimeCarbon.datetime_utc <= end_time
        ).order_by(WattTimeCarbon.datetime_utc)

        return session.exec(statement).all()

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch data from WattTime: {str(e)}"
        )


@router.post("/carbon/fetch-range/")
def fetch_and_store_range(
        region: str,
        start_time: datetime,
        end_time: datetime,
        background_tasks: BackgroundTasks,
        session: Session = Depends(get_managed_session)
):
    """
    Explicitly trigger a fetch for a time range and store it.
    Useful for pre-caching historical data for simulations.
    """
    background_tasks.add_task(
        fetch_range_task,
        region, start_time, end_time, session
    )
    return {"message": "Fetch job started in background"}


def fetch_range_task(region: str, start_time: datetime, end_time: datetime, session: Session):
    """Background task to fetch and store a range of carbon data."""
    try:
        df = watttime_service.get_historical_data(region, start_time, end_time)
        
        if df.empty:
            logging.warning(f"No data found for {region} from {start_time} to {end_time}")
            return

        for _, row in df.iterrows():
            carbon_entry = WattTimeCarbon(
                region=region,
                datetime_utc=row['datetime_utc'].to_pydatetime(),
                percent=row.get('percent', 0),
                moer=row.get('moer', 0.0),
            )
            session.merge(carbon_entry)

        session.commit()
        logging.info(f"Successfully fetched and stored carbon data for {region} from {start_time} to {end_time}")
    except Exception as e:
        logging.error(f"Background fetch failed: {e}")


@router.get("/region-from-loc/")
def get_region_from_loc(signal_type: str, latitude: float, longitude: float):
    """
    Get the Region (Balancing Authority) for a given latitude and longitude.
    """
    region = watttime_service.get_region_from_loc(signal_type, latitude, longitude)
    if region:
        return {"region": region}
    else:
        raise HTTPException(status_code=404, detail="Could not determine region for location.")


@router.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}
