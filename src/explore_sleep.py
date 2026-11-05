"""This module provides functionality to explore sleep data using the Garth API."""
from datetime import date

from garmin_client import get_sleep_data

if __name__ == "__main__":
    sleep_data = get_sleep_data(target_date=date.today())
    print(f"Sleep data for {date.today()}: {sleep_data}")
