import os
import openmeteo_requests
import pathlib
import pandas as pd
import requests

import requests_cache
from retry_requests import retry
from cron.settings_utils import get_coordinates, get_setting
from cron.settings import settings


def main():
    latitude, longitude = get_coordinates()

    # Setup session with caching and retry
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    # Type ignore for the session type mismatch
    openmeteo = openmeteo_requests.Client(
        session=retry_session)  # type: ignore

    models_path = get_setting('models_path', './config/models.csv')
    models_df = pd.read_csv(models_path)
    models = [row['name'] for _, row in models_df.iterrows()]

    for model in models:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ["temperature_2m"],
            "timezone": "Europe/Berlin",
            "models": [model]
        }

        try:
            responses = openmeteo.weather_api(url, params=params)
        except Exception as e:
            if "No data is available for this location" in str(e):
                print(
                    f"Model '{model}' has no data for location {latitude}N {longitude}E")
            continue


if __name__ == "__main__":
    main()
