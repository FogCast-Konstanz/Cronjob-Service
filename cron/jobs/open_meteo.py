import datetime
import os
import openmeteo_requests

import requests_cache
import pandas as pd
from retry_requests import retry

from cron.jobs.cronjob_base import CronjobBase
from cron.jobs.toDataFrame import toDataFrame
from cron.settings import settings

class OpenMeteoCronjob(CronjobBase):

    def __init__(self):
        super().__init__()
        self._lastDataDirectory = None

        models_df = pd.read_csv(settings.model_ids_path)
        self._models = {row['id']: row['name'] for _, row in models_df.iterrows()}

        hourly_fields_df = pd.read_csv(settings.hourly_fields_path)
        self._hourly_fields = [row['field'] for _, row in hourly_fields_df.iterrows()]

    def start(self, dt: datetime) -> bool:
        cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
        retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
        openmeteo = openmeteo_requests.Client(session = retry_session)

        # Make sure all required weather variables are listed here
        # The order of variables in hourly or daily is important to assign them correctly below
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": settings.latitude,
            "longitude": settings.longitude,
            "hourly": self._hourly_fields,
            "timezone": "Europe/Berlin",
            "models": self._models.values()
        }
        responses = openmeteo.weather_api(url, params=params)

        data_directory = os.path.join(settings.data_dir, dt.strftime("%Y-%m-%dT%H-%M-%S"))

        if not os.path.exists(data_directory):
            os.makedirs(data_directory)

        for (i, response) in enumerate(responses):
            model_id = response.Model()
            model = self._models[model_id]

            print("Received data for model: {}".format(model))

            df = toDataFrame(response)
            df.to_csv("{}/{}.csv".format(data_directory, model), index=False)
            
        self._lastDataDirectory = data_directory

    def cleanUpAfterError(self):
        if self._lastDataDirectory is not None:
            os.rmdir(self._lastDataDirectory)
